"""Shipments router — CRUD + workflow transitions + document uploads.

Workflow (enforced server-side):
  order_placed --(vendor invoice uploaded)--> under_production
  under_production --(status=in_transit; needs packing list + shipper)--> in_transit
  in_transit --(goods confirmed / status=completed; needs shipper invoice)--> completed
ImportFlow admins may override the status directly (e.g. to correct mistakes).
"""
import datetime as _dt
import time
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from .. import models, auth, eta_alerts, mailer, finance
from ..activity import log_action, notify_users
from ..files import validate_upload, file_response
from ..schemas import ShipmentCreate, ShipmentUpdate

router = APIRouter(prefix="/api/shipments", tags=["shipments"])

STATUS_ORDER = ["order_placed", "under_production", "in_transit", "completed"]
COMPANIES = {"facade", "davinci", "doortec"}


def _file_meta(f):
    """File metadata without base64 payload."""
    if isinstance(f, dict) and f:
        meta = {k: f.get(k) for k in ("name", "size", "type", "uploaded")}
        meta["hasData"] = bool(f.get("data"))
        return meta
    return None


def _cost_out(c):
    if not c:
        return None
    out = {k: v for k, v in c.items() if k != "docs"}
    out["docs"] = [_file_meta(d) for d in c.get("docs") or []]
    return out


def _out(s: models.Shipment) -> dict:
    return {
        "id": s.id,
        "ref": s.ref,
        "companyId": s.company_id,
        "projectId": s.project_id,
        "category": s.category,
        "vendorId": s.vendor_id,
        "shipperId": s.shipper_id,
        "status": s.status,
        "paymentTerms": s.payment_terms,
        "eta": s.eta,
        "shipMethod": s.ship_method,
        "description": s.description,
        "productionDays": s.production_days,
        "value": s.value,
        "currency": s.currency,
        "vendorInvoice": _file_meta(s.vendor_invoice),
        "packingList": _file_meta(s.packing_list),
        "shipperInvoice": _file_meta(s.shipper_invoice),
        "goodsConfirmed": s.goods_confirmed,
        "etaAlertsOn": bool((s.eta_alerts or {}).get("enabled")),
        "clearingAgentId": s.clearing_agent_id,
        "vendorPayments": s.vendor_payments or [],
        "vendorPaid": finance.vendor_paid(s),
        "vendorBalance": finance.vendor_balance(s),
        "vendorPayStatus": finance.vendor_status(s),
        "vendorPaymentDue": finance.payment_due(s),
        "shippingCost": _cost_out(s.shipping_cost),
        "clearingCost": _cost_out(s.clearing_cost),
        "dates": s.dates or {},
        "created": s.created,
        "updated": s.updated,
    }


def _next_ref(db: Session) -> str:
    """IMP-YYYY-NNN, per-year max + 1. The old count()+1 scheme reused refs
    after a deletion and was hard-coded to 2026."""
    prefix = f"IMP-{_dt.date.today().year}-"
    max_n = 0
    for (ref,) in db.query(models.Shipment.ref).filter(models.Shipment.ref.like(f"{prefix}%")).all():
        try:
            max_n = max(max_n, int(ref[len(prefix):]))
        except (TypeError, ValueError):
            continue
    return f"{prefix}{max_n + 1:03d}"


def _get(db: Session, shipment_id: str) -> models.Shipment:
    s = db.query(models.Shipment).filter(models.Shipment.id == shipment_id).first()
    if not s:
        raise HTTPException(404, "Shipment not found")
    return s


@router.get("")
def list_shipments(
    company: Optional[str] = None,
    status: Optional[str] = None,
    user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    q = db.query(models.Shipment).order_by(models.Shipment.created.desc())
    if company and company != "All":
        q = q.filter(models.Shipment.company_id == company)
    if status and status != "All":
        q = q.filter(models.Shipment.status == status)
    return [_out(s) for s in q.all()]


@router.post("")
def create_shipment(
    body: ShipmentCreate,
    user: models.User = Depends(auth.require_importflow_editor),
    db: Session = Depends(get_db),
):
    if body.companyId not in COMPANIES:
        raise HTTPException(400, "Company is required")
    if not body.category:
        raise HTTPException(400, "Category is required")
    if not body.vendorId or not db.query(models.Vendor).filter(models.Vendor.id == body.vendorId).first():
        raise HTTPException(400, "Vendor is required")
    if body.projectId and not db.query(models.Project).filter(models.Project.id == body.projectId).first():
        raise HTTPException(400, "Project not found")
    if not body.description or not body.description.strip():
        raise HTTPException(400, "Description is required")
    if body.value is not None and body.value < 0:
        raise HTTPException(400, "Value cannot be negative")
    now = int(time.time() * 1000)
    s = models.Shipment(
        id=uuid.uuid4().hex[:12],
        ref=_next_ref(db),
        company_id=body.companyId,
        project_id=body.projectId or None,
        category=body.category,
        vendor_id=body.vendorId,
        shipper_id=None,
        status="order_placed",
        payment_terms=None,
        eta="",
        ship_method="",
        description=body.description.strip(),
        production_days=body.productionDays or "",
        value=float(body.value or 0),
        currency=body.currency or "USD",
        vendor_invoice=None,
        packing_list=None,
        shipper_invoice=None,
        goods_confirmed=False,
        dates={"created": now},
        created=now,
        updated=now,
    )
    db.add(s)
    log_action(db, user, "shipment.created", f"Created shipment {s.ref} ({body.description.strip()[:40]})", "📦")
    notify_users(db, db.query(models.User).filter(models.User.active == True).all(),  # noqa: E712
                 f"New shipment {s.ref} created by {user.name}", "info", "📦", exclude_user=user)
    db.commit()
    db.refresh(s)
    return _out(s)


@router.get("/{shipment_id}/files/{kind}")
def download_file(
    shipment_id: str,
    kind: str,
    user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    s = _get(db, shipment_id)
    field = {"vendorInvoice": s.vendor_invoice, "packingList": s.packing_list, "shipperInvoice": s.shipper_invoice}.get(kind)
    if not field:
        raise HTTPException(404, "File not uploaded")
    return file_response(field, "document.pdf")


@router.put("/{shipment_id}")
def update_shipment(
    shipment_id: str,
    body: ShipmentUpdate,
    user: models.User = Depends(auth.require_importflow_editor),
    db: Session = Depends(get_db),
):
    s = _get(db, shipment_id)
    is_admin = auth.importflow_role(user) == "admin"
    now = int(time.time() * 1000)
    old_status = s.status
    old_eta = s.eta or ""
    dates = dict(s.dates or {})
    data = body.model_dump(exclude_none=True)

    if s.status == "completed" and not is_admin and set(data) - {"productionDays"}:
        raise HTTPException(400, "This shipment is completed; only an ImportFlow admin can change it")

    if "productionDays" in data:
        s.production_days = data["productionDays"].strip()

    # --- documents ---
    if "vendorInvoice" in data:
        s.vendor_invoice = validate_upload(data["vendorInvoice"], "Vendor invoice")
        dates["invoiceUploaded"] = now
        if s.status == "order_placed":
            s.status = "under_production"
    if "packingList" in data:
        if s.status == "order_placed" and not is_admin:
            raise HTTPException(400, "Upload the vendor invoice before the packing list")
        s.packing_list = validate_upload(data["packingList"], "Packing list")
        dates["packingReady"] = now
    if "shipperInvoice" in data:
        if STATUS_ORDER.index(s.status) < STATUS_ORDER.index("in_transit") and not is_admin:
            raise HTTPException(400, "Goods must be shipped before uploading the shipper invoice")
        s.shipper_invoice = validate_upload(data["shipperInvoice"], "Shipper invoice")
        dates["shipperInvoiced"] = now

    # --- shipping details (no implicit status change) ---
    if "shipperId" in data:
        sid = data["shipperId"] or None
        if sid and not db.query(models.Shipper).filter(models.Shipper.id == sid).first():
            raise HTTPException(400, "Shipper not found")
        if sid != s.shipper_id and s.status in ("in_transit", "completed") and not is_admin:
            raise HTTPException(400, "The shipper cannot be changed after goods have shipped")
        s.shipper_id = sid
        if sid:
            dates["shipperSelected"] = now
    if "paymentTerms" in data:
        s.payment_terms = data["paymentTerms"] or None
    if "eta" in data:
        s.eta = data["eta"].strip()
    if "shipMethod" in data:
        s.ship_method = data["shipMethod"]

    # --- status transitions ---
    target = data.get("status")
    if data.get("goodsConfirmed") is True:
        target = target or "completed"
    if "goodsConfirmed" in data and not data["goodsConfirmed"]:
        s.goods_confirmed = False

    if target and target != s.status:
        if target == "in_transit" and s.status == "under_production":
            if not s.packing_list:
                raise HTTPException(400, "Upload the packing list before shipping")
            if not s.shipper_id:
                raise HTTPException(400, "Assign a shipper before shipping")
            s.status = "in_transit"
            dates["shipped"] = now
        elif target == "completed" and s.status == "in_transit":
            if not s.shipper_invoice:
                raise HTTPException(400, "Upload the shipper invoice before closing the cycle")
            if not is_admin:
                if not _cost_total(s.shipping_cost):
                    raise HTTPException(400, "Record the shipping cost before confirming the goods")
                if not s.clearing_agent_id or not _cost_total(s.clearing_cost):
                    raise HTTPException(400, "Record the clearing agent and clearing cost before confirming the goods")
            s.status = "completed"
            s.goods_confirmed = True
            dates["closed"] = now
        elif is_admin:
            # manual override by an ImportFlow admin
            s.status = target
            if target == "in_transit":
                dates.setdefault("shipped", now)
            if target == "completed":
                s.goods_confirmed = True
                dates.setdefault("closed", now)
        else:
            raise HTTPException(
                400, f"Cannot move from {old_status.replace('_', ' ')} to {target.replace('_', ' ')}"
            )
    elif target == "completed" and s.status == "completed":
        s.goods_confirmed = True

    s.dates = dates
    s.updated = now
    if s.status != old_status:
        log_action(db, user, "shipment.status", f"{s.ref}: {old_status.replace('_', ' ').title()} to {s.status.replace('_', ' ').title()}", "🔄")
        notify_users(db, db.query(models.User).filter(models.User.active == True).all(),  # noqa: E712
                     f"Shipment {s.ref} is now {s.status.replace('_', ' ')}", "success", "🔄", exclude_user=user)
        status_changed_from = old_status
    else:
        status_changed_from = None
    if "vendorInvoice" in data:
        log_action(db, user, "shipment.upload", f"{s.ref}: vendor invoice uploaded", "📄")
    if "packingList" in data:
        log_action(db, user, "shipment.upload", f"{s.ref}: packing list uploaded", "📄")
    if "shipperInvoice" in data:
        log_action(db, user, "shipment.upload", f"{s.ref}: shipper invoice uploaded", "📄")
    db.commit()
    if status_changed_from:
        try:
            from .. import notify_mail
            notify_mail.shipment_status_changed(db, s, status_changed_from, user)
            db.commit()
        except Exception:  # email must never break saving
            db.rollback()
    # ETA moved: tell the alert list straight away (reminders re-arm for the new date)
    if (s.eta or "") != old_eta and s.status != "completed":
        a = eta_alerts.settings_of(s)
        if a["enabled"] and a["onChange"] and a["recipients"]:
            eta_alerts.send_alert(db, s, "changed", old_eta=old_eta)
            db.commit()
    db.refresh(s)
    return _out(s)


# ---------------------------------------------------------------------------
# ETA email alerts
# ---------------------------------------------------------------------------

def _alerts_out(db, s):
    logs = (db.query(models.EmailLog).filter(models.EmailLog.shipment_id == s.id)
            .order_by(models.EmailLog.ts.desc()).limit(8).all())
    return {**eta_alerts.public_settings(s), "email": mailer.status(),
            "log": [{"to": l.to, "subject": l.subject, "kind": l.kind, "status": l.status, "error": l.error, "ts": l.ts} for l in logs]}


@router.get("/{shipment_id}/eta-alerts")
def get_eta_alerts(shipment_id: str, user: models.User = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    return _alerts_out(db, _get(db, shipment_id))


@router.put("/{shipment_id}/eta-alerts")
def put_eta_alerts(shipment_id: str, body: dict, user: models.User = Depends(auth.require_importflow_editor),
                   db: Session = Depends(get_db)):
    s = _get(db, shipment_id)
    current = eta_alerts.settings_of(s)
    try:
        new = eta_alerts.clean_settings(body or {}, current)
    except (ValueError, TypeError) as e:
        raise HTTPException(400, str(e))
    s.eta_alerts = new
    s.updated = int(time.time() * 1000)
    on = "on" if new["enabled"] else "off"
    log_action(db, user, "shipment.eta_alerts", f"{s.ref}: ETA email alerts {on} ({len(new['recipients'])} recipient(s))", "📧")
    db.commit()
    # anything already due (e.g. ETA is tomorrow and alerts were just switched on) goes now
    for kind, days in eta_alerts.due(s):
        ok, _ = eta_alerts.send_alert(db, s, kind, days)
        if ok:
            eta_alerts.mark_sent(s, kind)
    db.commit()
    db.refresh(s)
    return _alerts_out(db, s)


@router.post("/{shipment_id}/eta-alerts/test")
def test_eta_alert(shipment_id: str, body: dict | None = None, user: models.User = Depends(auth.require_importflow_editor),
                   db: Session = Depends(get_db)):
    s = _get(db, shipment_id)
    rec = (body or {}).get("recipients") or eta_alerts.settings_of(s)["recipients"] or [user.email]
    ok, err = eta_alerts.send_alert(db, s, "test", recipients=rec)
    db.commit()
    if not ok:
        raise HTTPException(503 if "set up" in err else 502, err)
    return {"ok": True, "sentTo": rec}


@router.delete("/{shipment_id}")
def delete_shipment(
    shipment_id: str,
    user: models.User = Depends(auth.require_importflow_editor),
    db: Session = Depends(get_db),
):
    s = _get(db, shipment_id)
    ref = s.ref
    db.delete(s)
    log_action(db, user, "shipment.deleted", f"Deleted shipment {ref}", "🗑")
    db.commit()
    return {"ok": True}



# ---------------------------------------------------------------------------
# Shipping & clearing costs (recorded while In Transit)
# ---------------------------------------------------------------------------

MAX_LINES = 25
MAX_CLEARING_DOCS = 10
_DATE = __import__("re").compile(r"^\d{4}-\d{2}-\d{2}$")


def _cost_total(c) -> float:
    return round(sum(float(l.get("amount") or 0) for l in (c or {}).get("lines") or []), 2)


def _fx_codes(db) -> set:
    from .settings import _out as fx_out, _row as fx_row
    return set(fx_out(fx_row(db))["rates"]) | {"NGN", "USD"}


def _clean_cost(raw: dict, current: dict | None, what: str, db, user) -> dict:
    if not isinstance(raw, dict):
        raise HTTPException(400, f"{what} must be an object")
    cur = dict(current or {})
    code = str(raw.get("currency") or cur.get("currency") or "NGN").upper().strip()
    if code not in _fx_codes(db):
        raise HTTPException(400, f"{what}: no exchange rate for {code}. Add it under Reports → Exchange rates first")
    lines_in = raw.get("lines", cur.get("lines") or [])
    if not isinstance(lines_in, list) or len(lines_in) > MAX_LINES:
        raise HTTPException(400, f"{what}: up to {MAX_LINES} cost lines")
    lines = []
    for i, l in enumerate(lines_in, start=1):
        label = str((l or {}).get("label") or "").strip()[:80]
        try:
            amount = round(float((l or {}).get("amount") or 0), 2)
        except (TypeError, ValueError):
            raise HTTPException(400, f"{what}, line {i}: amount must be a number")
        if amount < 0 or amount != amount or amount > 1e12:
            raise HTTPException(400, f"{what}, line {i}: amount must be zero or more")
        if not label and amount:
            raise HTTPException(400, f"{what}, line {i}: give the charge a name")
        if label or amount:
            lines.append({"id": str((l or {}).get("id") or uuid.uuid4().hex[:8])[:16], "label": label, "amount": amount})
    paid = bool(raw.get("paid", cur.get("paid", False)))
    paid_on = str(raw.get("paidOn", cur.get("paidOn") or "") or "").strip()
    if paid_on and not _DATE.match(paid_on):
        raise HTTPException(400, f"{what}: payment date must be a date")
    out = {
        **cur, "currency": code, "lines": lines, "total": round(sum(l["amount"] for l in lines), 2),
        "invoiceRef": str(raw.get("invoiceRef", cur.get("invoiceRef") or "") or "").strip()[:80],
        "note": str(raw.get("note", cur.get("note") or "") or "").strip()[:500],
        "paid": paid, "paidOn": paid_on if paid else "",
        "updated": int(time.time() * 1000), "updatedBy": user.name,
    }
    return out


def _can_edit_costs(s, user):
    is_admin = auth.importflow_role(user) == "admin"
    if s.status == "in_transit" or is_admin:
        return
    if s.status == "completed":
        raise HTTPException(400, "This shipment is completed; only an ImportFlow admin can change its costs")
    raise HTTPException(400, "Costs are recorded once the goods are shipped (In Transit)")


@router.put("/{shipment_id}/costs")
def update_costs(shipment_id: str, body: dict, user: models.User = Depends(auth.require_importflow_editor),
                 db: Session = Depends(get_db)):
    s = _get(db, shipment_id)
    _can_edit_costs(s, user)
    now = int(time.time() * 1000)
    dates = dict(s.dates or {})
    msgs = []
    if "clearingAgentId" in body:
        aid = body["clearingAgentId"] or None
        if aid and not db.query(models.ClearingAgent).filter(models.ClearingAgent.id == aid).first():
            raise HTTPException(400, "Clearing agent not found")
        s.clearing_agent_id = aid
    if "shipping" in body:
        s.shipping_cost = _clean_cost(body["shipping"], s.shipping_cost, "Shipping cost", db, user)
        if s.shipping_cost["total"] > 0:
            dates.setdefault("shippingCosted", now)
        msgs.append(f"shipping cost {s.shipping_cost['currency']} {s.shipping_cost['total']:,.2f}")
    if "clearing" in body:
        new = _clean_cost(body["clearing"], s.clearing_cost, "Clearing cost", db, user)
        new["docs"] = (s.clearing_cost or {}).get("docs") or []
        if new["total"] > 0 and not s.clearing_agent_id:
            raise HTTPException(400, "Choose the clearing agent first")
        s.clearing_cost = new
        if new["total"] > 0:
            dates.setdefault("clearingCosted", now)
        msgs.append(f"clearing cost {new['currency']} {new['total']:,.2f}")
    s.dates = dates
    s.updated = now
    if msgs:
        log_action(db, user, "shipment.costs", f"{s.ref}: " + ", ".join(msgs), "💰")
    db.commit()
    db.refresh(s)
    return _out(s)


@router.post("/{shipment_id}/clearing-docs")
def add_clearing_doc(shipment_id: str, body: dict, user: models.User = Depends(auth.require_importflow_editor),
                     db: Session = Depends(get_db)):
    s = _get(db, shipment_id)
    _can_edit_costs(s, user)
    c = dict(s.clearing_cost or {"currency": "NGN", "lines": [], "total": 0})
    docs = list(c.get("docs") or [])
    if len(docs) >= MAX_CLEARING_DOCS:
        raise HTTPException(400, f"Up to {MAX_CLEARING_DOCS} clearing documents per shipment")
    f = validate_upload(body.get("file"), "Clearing document")
    label = str(body.get("label") or "").strip()[:60]
    if label:
        f["label"] = label
    docs.append(f)
    c["docs"] = docs
    s.clearing_cost = c
    s.updated = int(time.time() * 1000)
    log_action(db, user, "shipment.upload", f"{s.ref}: clearing document {f.get('name')} uploaded", "📄")
    db.commit()
    db.refresh(s)
    return _out(s)


def _clearing_doc(s, i):
    docs = (s.clearing_cost or {}).get("docs") or []
    if i < 0 or i >= len(docs):
        raise HTTPException(404, "Document not found")
    return docs


@router.get("/{shipment_id}/clearing-docs/{i}")
def get_clearing_doc(shipment_id: str, i: int, user: models.User = Depends(auth.get_current_user),
                     db: Session = Depends(get_db)):
    s = _get(db, shipment_id)
    return file_response(_clearing_doc(s, i)[i], "clearing-document")


@router.delete("/{shipment_id}/clearing-docs/{i}")
def delete_clearing_doc(shipment_id: str, i: int, user: models.User = Depends(auth.require_importflow_editor),
                        db: Session = Depends(get_db)):
    s = _get(db, shipment_id)
    _can_edit_costs(s, user)
    docs = _clearing_doc(s, i)
    name = docs[i].get("name")
    c = dict(s.clearing_cost)
    c["docs"] = docs[:i] + docs[i + 1:]
    s.clearing_cost = c
    log_action(db, user, "shipment.upload", f"{s.ref}: clearing document {name} removed", "🗑")
    db.commit()
    db.refresh(s)
    return _out(s)



# ---------------------------------------------------------------------------
# Vendor payments (deposit / balance), in the shipment's currency
# ---------------------------------------------------------------------------

PAY_KINDS = ("Deposit", "Balance", "Full payment", "Other")


@router.post("/{shipment_id}/vendor-payments")
def add_vendor_payment(shipment_id: str, body: dict, user: models.User = Depends(auth.require_importflow_editor),
                       db: Session = Depends(get_db)):
    s = _get(db, shipment_id)
    if s.status == "completed" and auth.importflow_role(user) != "admin":
        raise HTTPException(400, "This shipment is completed; only an ImportFlow admin can add payments")
    try:
        amount = round(float(body.get("amount")), 2)
    except (TypeError, ValueError):
        raise HTTPException(400, "Amount must be a number")
    if not amount > 0:
        raise HTTPException(400, "Amount must be more than zero")
    if amount > finance.vendor_balance(s) + 0.005 and not body.get("allowOverpay"):
        raise HTTPException(400, f"That's more than the {s.currency} {finance.vendor_balance(s):,.2f} still owed")
    day = str(body.get("date") or _dt.date.today().isoformat())[:10]
    try:
        _dt.date.fromisoformat(day)
    except ValueError:
        raise HTTPException(400, "Payment date must be a date")
    kind = body.get("kind") if body.get("kind") in PAY_KINDS else "Other"
    pays = list(s.vendor_payments or [])
    if len(pays) >= 30:
        raise HTTPException(400, "Up to 30 payments per shipment")
    pays.append({"id": uuid.uuid4().hex[:10], "date": day, "amount": amount, "kind": kind,
                 "ref": str(body.get("ref") or "").strip()[:80], "note": str(body.get("note") or "").strip()[:300],
                 "by": user.name, "ts": int(time.time() * 1000)})
    s.vendor_payments = sorted(pays, key=lambda p: p["date"])
    s.updated = int(time.time() * 1000)
    left = finance.vendor_balance(s)
    log_action(db, user, "shipment.vendor_payment",
               f"{s.ref}: paid vendor {s.currency} {amount:,.2f} ({kind})" + (" · fully paid" if left <= 0.005 else f" · {s.currency} {left:,.2f} left"), "💳")
    db.commit()
    db.refresh(s)
    return _out(s)


@router.delete("/{shipment_id}/vendor-payments/{payment_id}")
def delete_vendor_payment(shipment_id: str, payment_id: str, user: models.User = Depends(auth.require_importflow_editor),
                          db: Session = Depends(get_db)):
    s = _get(db, shipment_id)
    if s.status == "completed" and auth.importflow_role(user) != "admin":
        raise HTTPException(400, "This shipment is completed; only an ImportFlow admin can change payments")
    pays = list(s.vendor_payments or [])
    gone = next((p for p in pays if p["id"] == payment_id), None)
    if not gone:
        raise HTTPException(404, "Payment not found")
    s.vendor_payments = [p for p in pays if p["id"] != payment_id]
    log_action(db, user, "shipment.vendor_payment", f"{s.ref}: removed vendor payment {s.currency} {gone['amount']:,.2f}", "🗑")
    db.commit()
    db.refresh(s)
    return _out(s)

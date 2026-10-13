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
from .. import models, auth
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
    if "vendorInvoice" in data:
        log_action(db, user, "shipment.upload", f"{s.ref}: vendor invoice uploaded", "📄")
    if "packingList" in data:
        log_action(db, user, "shipment.upload", f"{s.ref}: packing list uploaded", "📄")
    if "shipperInvoice" in data:
        log_action(db, user, "shipment.upload", f"{s.ref}: shipper invoice uploaded", "📄")
    db.commit()
    db.refresh(s)
    return _out(s)


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

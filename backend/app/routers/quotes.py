"""Quotes router — native quotations module backed by the server-side pricing engine.

Implements the audit P0 recommendation: pricing logic and numbering live on the
server (per-record persistence, no last-write-wins blob), quote numbers are
generated per-year max+1 (fixes audit R2), and the markup floor is enforced
server-side (audit P2 hardening).
"""
import time
import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from .. import models, auth, pricing
from ..activity import log_action, notify_users
from ..schemas import (
    QuoteCreate, QuoteUpdate, RevisionCreate, RevisionUpdate, StatusUpdate, CatalogUpdate,
)

router = APIRouter(prefix="/api/quotes", tags=["quotes"])

CATALOG_KEYS = {"products", "subs", "hwItems", "hwKits", "sf", "mosqRates", "acpPanels", "gc", "rates", "settings"}
STATUSES = {"draft", "sent", "won", "lost"}


# ---------------------------------------------------------------------------
# Catalogue: defaults + admin overrides
# ---------------------------------------------------------------------------

def get_catalog(db: Session) -> dict:
    merged = {k: v for k, v in pricing.DEFAULT_CATALOG.items()}
    overrides = {s.key: s.value for s in db.query(models.FacadeSetting).all()}
    for k, v in overrides.items():
        if k in CATALOG_KEYS:
            merged[k] = v
    return merged


@router.get("/catalog")
def read_catalog(user: models.User = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    overrides = [s.key for s in db.query(models.FacadeSetting).all() if s.key in CATALOG_KEYS]
    return {"values": get_catalog(db), "overridden": overrides}


@router.put("/catalog/{key}")
def update_catalog(
    key: str,
    body: CatalogUpdate,
    user: models.User = Depends(auth.require_admin),
    db: Session = Depends(get_db),
):
    if key not in CATALOG_KEYS:
        raise HTTPException(400, f"Unknown catalogue key. Valid: {sorted(CATALOG_KEYS)}")
    row = db.query(models.FacadeSetting).filter(models.FacadeSetting.key == key).first()
    if row:
        row.value = body.value
        row.updated = int(time.time() * 1000)
    else:
        row = models.FacadeSetting(key=key, value=body.value, updated=int(time.time() * 1000))
        db.add(row)
    log_action(db, user, "quote.catalog", f"Updated pricing catalogue: {key}", "⚙️")
    db.commit()
    return {"ok": True, "key": key, "values": get_catalog(db)}


def _settings(catalog: dict) -> dict:
    return catalog.get("settings") or pricing.SETTINGS_DEF


def _clamp_markup(markup, catalog: dict) -> float:
    """Enforce the configurable markup floor server-side (audit hardening)."""
    s = _settings(catalog)
    try:
        m = float(markup)
    except (TypeError, ValueError):
        m = float(s.get("defaultMarkup", 100))
    floor = float(s.get("minMarkup", 70))
    return max(m, floor)


# ---------------------------------------------------------------------------
# Stateless calculation (live preview)
# ---------------------------------------------------------------------------

@router.post("/calculate")
def calculate(body: dict, user: models.User = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    catalog = get_catalog(db)
    items = body.get("items") or []
    s = _settings(catalog)
    markup = body.get("markupPct", s.get("defaultMarkup", 100))
    if markup is None:
        markup = s.get("defaultMarkup", 100)
    markup = _clamp_markup(markup, catalog)
    vat = body.get("vatPct")
    vat = float(vat) if vat is not None else float(s.get("vatRate", 7.5))
    totals = pricing.calc_totals(
        items, markup, vat,
        rates=catalog.get("rates"), gc=catalog.get("gc"), acp_panels=catalog.get("acpPanels"),
        hw_items=catalog.get("hwItems"), hw_kits=catalog.get("hwKits"), sf=catalog.get("sf"),
    )
    return {"markupPct": markup, "vatPct": vat, **totals}


# ---------------------------------------------------------------------------
# Serializers
# ---------------------------------------------------------------------------

def _rev_out(r: models.QuoteRevision, include_items: bool = True, db: Session | None = None) -> dict:
    d = {
        "id": r.id,
        "quoteId": r.quote_id,
        "rev": r.rev,
        "status": r.status,
        "markupPct": r.markup_pct,
        "vatPct": r.vat_pct,
        "validityDays": r.validity_days,
        "paymentTerms": r.payment_terms,
        "note": r.note,
        "cost": r.cost,
        "mkAmt": r.mk_amt,
        "sub": r.sub,
        "vatAmt": r.vat_amt,
        "total": r.total,
        "created": r.created,
        "updated": r.updated,
    }
    if include_items:
        items = r.items or []
        if db is not None and items:
            # attach computed BOM + labels on read (storage keeps inputs only)
            catalog = get_catalog(db)
            totals = pricing.calc_totals(
                items, r.markup_pct, r.vat_pct,
                rates=catalog.get("rates"), gc=catalog.get("gc"), acp_panels=catalog.get("acpPanels"),
                hw_items=catalog.get("hwItems"), hw_kits=catalog.get("hwKits"), sf=catalog.get("sf"),
            )
            items = totals["items"]
        d["items"] = items
    return d


def _quote_out(q: models.Quote, revisions: list | None = None) -> dict:
    d = {
        "id": q.id,
        "number": q.number,
        "projectId": q.project_id,
        "projectName": q.project_name,
        "clientName": q.client_name,
        "clientPhone": q.client_phone,
        "clientEmail": q.client_email,
        "salesPerson": q.sales_person,
        "notes": q.notes,
        "created": q.created,
        "updated": q.updated,
    }
    if revisions is not None:
        d["revisions"] = revisions
        latest = max(revisions, key=lambda r: r["rev"]) if revisions else None
        d["latest"] = latest
        d["status"] = latest["status"] if latest else "draft"
        d["total"] = latest["total"] if latest else 0
    return d


def _quote_revisions(db: Session, quote_id: str, include_items: bool = False) -> list:
    rows = (
        db.query(models.QuoteRevision)
        .filter(models.QuoteRevision.quote_id == quote_id)
        .order_by(models.QuoteRevision.rev.desc())
        .all()
    )
    return [_rev_out(r, include_items=include_items, db=db if include_items else None) for r in rows]


def _get_quote(db: Session, quote_id: str) -> models.Quote:
    q = db.query(models.Quote).filter(models.Quote.id == quote_id).first()
    if not q:
        raise HTTPException(404, "Quote not found")
    return q


def _notify_admins(db, actor, message, kind="info", icon="🔔"):
    admins = db.query(models.User).filter(models.User.platform_role == "admin", models.User.active == True).all()  # noqa: E712
    notify_users(db, admins, message, kind, icon, exclude_user=actor)


# ---------------------------------------------------------------------------
# Quote CRUD
# ---------------------------------------------------------------------------

@router.get("")
def list_quotes(user: models.User = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    quotes = db.query(models.Quote).order_by(models.Quote.updated.desc()).all()
    out = []
    for q in quotes:
        revs = _quote_revisions(db, q.id)
        out.append(_quote_out(q, revs))
    return out


@router.post("")
def create_quote(
    body: QuoteCreate,
    user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    now = int(time.time() * 1000)
    catalog = get_catalog(db)
    s = _settings(catalog)

    numbers = [r[0] for r in db.query(models.Quote.number).all()]
    number = pricing.next_quote_number(numbers)

    project_name = ""
    if body.projectId:
        p = db.query(models.Project).filter(models.Project.id == body.projectId).first()
        project_name = p.name if p else ""

    markup = _clamp_markup(body.markupPct if body.markupPct is not None else s.get("defaultMarkup", 100), catalog)
    vat = float(body.vatPct) if body.vatPct is not None else float(s.get("vatRate", 7.5))

    totals = pricing.calc_totals(
        body.items, markup, vat,
        rates=catalog.get("rates"), gc=catalog.get("gc"), acp_panels=catalog.get("acpPanels"),
        hw_items=catalog.get("hwItems"), hw_kits=catalog.get("hwKits"), sf=catalog.get("sf"),
    )

    q = models.Quote(
        id=uuid.uuid4().hex[:12],
        number=number,
        project_id=body.projectId,
        project_name=project_name,
        client_name=body.clientName or "",
        client_phone=body.clientPhone or "",
        client_email=body.clientEmail or "",
        sales_person=body.salesPerson or "",
        notes=body.notes or "",
        created=now,
        updated=now,
    )
    rev = models.QuoteRevision(
        id=uuid.uuid4().hex[:12],
        quote_id=q.id,
        rev=0,
        status="draft",
        items=[{k: v for k, v in it.items() if k != "bom"} for it in totals["items"]],
        markup_pct=markup,
        vat_pct=vat,
        validity_days=int(s.get("validity", 14)),
        payment_terms=s.get("paymentTerms", ""),
        cost=totals["cost"],
        mk_amt=totals["mkAmt"],
        sub=totals["sub"],
        vat_amt=totals["vat"],
        total=totals["total"],
        created=now,
        updated=now,
    )
    db.add(q)
    db.add(rev)
    log_action(db, user, "quote.created", f"Created quote {number} for {q.client_name or 'unnamed client'}", "🧾")
    _notify_admins(db, user, f"{user.name} created quote {number}", "info", "🧾")
    db.commit()
    db.refresh(q)
    return _quote_out(q, _quote_revisions(db, q.id, include_items=True))


@router.get("/{quote_id}")
def get_quote(quote_id: str, user: models.User = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    q = _get_quote(db, quote_id)
    return _quote_out(q, _quote_revisions(db, q.id, include_items=True))


@router.put("/{quote_id}")
def update_quote(
    quote_id: str,
    body: QuoteUpdate,
    user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    q = _get_quote(db, quote_id)
    data = body.model_dump(exclude_none=True)
    if "projectId" in data:
        p = db.query(models.Project).filter(models.Project.id == data["projectId"]).first()
        q.project_name = p.name if p else ""
    field_map = {
        "clientName": "client_name", "clientPhone": "client_phone",
        "clientEmail": "client_email", "salesPerson": "sales_person", "notes": "notes",
    }
    for src, dst in field_map.items():
        if src in data:
            setattr(q, dst, data[src])
    q.updated = int(time.time() * 1000)
    log_action(db, user, "quote.updated", f"Updated quote {q.number}", "✏️")
    db.commit()
    db.refresh(q)
    return _quote_out(q, _quote_revisions(db, q.id))


@router.delete("/{quote_id}")
def delete_quote(quote_id: str, user: models.User = Depends(auth.require_admin), db: Session = Depends(get_db)):
    q = _get_quote(db, quote_id)
    db.query(models.QuoteRevision).filter(models.QuoteRevision.quote_id == quote_id).delete()
    log_action(db, user, "quote.deleted", f"Deleted quote {q.number}", "🗑")
    db.delete(q)
    db.commit()
    return {"ok": True}


# ---------------------------------------------------------------------------
# Revisions
# ---------------------------------------------------------------------------

def _recompute(db, rev: models.QuoteRevision):
    catalog = get_catalog(db)
    totals = pricing.calc_totals(
        rev.items or [], rev.markup_pct, rev.vat_pct,
        rates=catalog.get("rates"), gc=catalog.get("gc"), acp_panels=catalog.get("acpPanels"),
        hw_items=catalog.get("hwItems"), hw_kits=catalog.get("hwKits"), sf=catalog.get("sf"),
    )
    rev.items = [{k: v for k, v in it.items() if k != "bom"} for it in totals["items"]]
    rev.cost = totals["cost"]
    rev.mk_amt = totals["mkAmt"]
    rev.sub = totals["sub"]
    rev.vat_amt = totals["vat"]
    rev.total = totals["total"]
    rev.updated = int(time.time() * 1000)


@router.post("/{quote_id}/revisions")
def create_revision(
    quote_id: str,
    body: RevisionCreate,
    user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    q = _get_quote(db, quote_id)
    latest = (
        db.query(models.QuoteRevision)
        .filter(models.QuoteRevision.quote_id == quote_id)
        .order_by(models.QuoteRevision.rev.desc())
        .first()
    )
    catalog = get_catalog(db)
    s = _settings(catalog)
    now = int(time.time() * 1000)

    src_items = body.items if body.items is not None else (latest.items if latest else [])
    markup = _clamp_markup(
        body.markupPct if body.markupPct is not None else (latest.markup_pct if latest else s.get("defaultMarkup", 100)),
        catalog,
    )
    vat = float(body.vatPct) if body.vatPct is not None else (latest.vat_pct if latest else float(s.get("vatRate", 7.5)))

    rev = models.QuoteRevision(
        id=uuid.uuid4().hex[:12],
        quote_id=quote_id,
        rev=(latest.rev + 1) if latest else 0,
        status="draft",
        items=src_items or [],
        markup_pct=markup,
        vat_pct=vat,
        validity_days=latest.validity_days if latest else int(s.get("validity", 14)),
        payment_terms=latest.payment_terms if latest else s.get("paymentTerms", ""),
        note=body.note or "",
        created=now,
        updated=now,
    )
    _recompute(db, rev)
    db.add(rev)
    q.updated = now
    log_action(db, user, "quote.revision", f"Created Rev.{rev.rev} for {q.number}", "🧾")
    db.commit()
    db.refresh(rev)
    return _rev_out(rev, include_items=True)


@router.put("/{quote_id}/revisions/{rev_id}")
def update_revision(
    quote_id: str,
    rev_id: str,
    body: RevisionUpdate,
    user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    q = _get_quote(db, quote_id)
    rev = db.query(models.QuoteRevision).filter(models.QuoteRevision.id == rev_id, models.QuoteRevision.quote_id == quote_id).first()
    if not rev:
        raise HTTPException(404, "Revision not found")

    data = body.model_dump(exclude_none=True)
    changed = False
    if "items" in data:
        rev.items = data["items"]
        changed = True
    if "markupPct" in data:
        catalog = get_catalog(db)
        rev.markup_pct = _clamp_markup(data["markupPct"], catalog)
        changed = True
    if "vatPct" in data:
        rev.vat_pct = float(data["vatPct"])
        changed = True
    if "note" in data:
        rev.note = data["note"]
    if changed:
        _recompute(db, rev)
        q.updated = int(time.time() * 1000)
        log_action(db, user, "quote.revision", f"Updated Rev.{rev.rev} of {q.number}", "✏️")
    db.commit()
    db.refresh(rev)
    return _rev_out(rev, include_items=True)


@router.post("/{quote_id}/revisions/{rev_id}/status")
def set_revision_status(
    quote_id: str,
    rev_id: str,
    body: StatusUpdate,
    user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    q = _get_quote(db, quote_id)
    rev = db.query(models.QuoteRevision).filter(models.QuoteRevision.id == rev_id, models.QuoteRevision.quote_id == quote_id).first()
    if not rev:
        raise HTTPException(404, "Revision not found")
    if body.status not in STATUSES:
        raise HTTPException(400, "Status must be one of: draft, sent, won, lost")
    old = rev.status
    rev.status = body.status
    rev.updated = int(time.time() * 1000)
    q.updated = rev.updated
    label = {"draft": "Draft", "sent": "Sent", "won": "Won", "lost": "Lost"}[body.status]
    log_action(db, user, "quote.status", f"{q.number} Rev.{rev.rev}: {old} -> {body.status}", "🔁")
    if body.status in ("sent", "won", "lost"):
        _notify_admins(db, user, f"{q.number} Rev.{rev.rev} marked {label} ({user.name})", "success" if body.status == "won" else "info", "🧾")
    db.commit()
    db.refresh(rev)
    return _rev_out(rev, include_items=True)

"""Quotes router — native quotations module backed by the server-side pricing engine.

Implements the audit P0 recommendation: pricing logic and numbering live on the
server (per-record persistence, no last-write-wins blob), quote numbers are
generated per-year max+1 (fixes audit R2), and the markup floor is enforced
server-side (audit P2 hardening).
"""
import datetime as _dt
import io
import time
import uuid
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ..database import get_db
from .. import models, auth, pricing, excel_export
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
        "logisticsCost": r.logistics_cost or 0,
        "logisticsLocation": r.logistics_location or "",
        "total": r.total,
        "itemsCount": len(r.items or []),
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
    rev.total = totals["total"] + float(rev.logistics_cost or 0)  # logistics rides on top of VAT
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


# ---------------------------------------------------------------------------
# Legacy facade migration (demo quotes out of localStorage into the platform)
# ---------------------------------------------------------------------------

def _ms(v, fallback=None):
    """Facade dates are ISO strings or ms; normalize to epoch ms."""
    if v is None:
        return fallback
    if isinstance(v, (int, float)):
        return int(v)
    s = str(v)
    try:
        if s.isdigit():
            return int(s)
        return int(_dt.datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp() * 1000)
    except ValueError:
        return fallback


def _migrate_revision(rev_in: dict, quote_in: dict, project_in: dict, legacy: dict, catalog: dict):
    """Map one facade revision onto a native QuoteRevision (totals recomputed with
    the facade's own catalog snapshot so migrated figures match the legacy app)."""
    settings = legacy.get("settings") or {}
    s = _settings(catalog)
    now = int(time.time() * 1000)
    created = _ms(rev_in.get("createdAt"), now)
    updated = _ms(rev_in.get("updatedAt"), created)

    items = rev_in.get("lineItems") or []
    if not isinstance(items, list):
        items = []
    items = [{k: v for k, v in it.items() if k != "bom"} for it in items]

    markup = rev_in.get("markupOverride")
    if markup is None:
        markup = settings.get("defaultMarkup", s.get("defaultMarkup", 100))
    try:
        markup = float(markup)
    except (TypeError, ValueError):
        markup = float(s.get("defaultMarkup", 100))
    # No floor clamp on import: keep the legacy document's figures exactly.

    vat = settings.get("vatRate", s.get("vatRate", 7.5))
    try:
        vat = float(vat)
    except (TypeError, ValueError):
        vat = 7.5

    validity = int(s.get("validity", 14))
    cu, vu = _ms(rev_in.get("createdAt")), _ms(rev_in.get("validUntil"))
    if cu and vu and vu > cu:
        validity = max(1, round((vu - cu) / 86400000))

    status = rev_in.get("status") if rev_in.get("status") in STATUSES else "draft"
    try:
        rev_no = int(rev_in.get("rev", 0))
    except (TypeError, ValueError):
        rev_no = 0

    logistics_cost = float(rev_in.get("logisticsCost") or 0) if rev_in.get("outsideLagos") else 0.0
    totals = pricing.calc_totals(
        items, markup, vat,
        rates=legacy.get("rates"), gc=legacy.get("gc"), acp_panels=legacy.get("acpPanels"),
        hw_items=legacy.get("hwItems"), hw_kits=legacy.get("hwKits"), sf=legacy.get("sf"),
        mosq_rates=legacy.get("mosqRates"),
    )

    return models.QuoteRevision(
        id=uuid.uuid4().hex[:12],
        quote_id=None,  # set by caller after the parent quote is added
        rev=rev_no,
        status=status,
        items=[{k: v for k, v in it.items() if k != "bom"} for it in totals["items"]],
        markup_pct=markup,
        vat_pct=vat,
        validity_days=validity,
        payment_terms=settings.get("paymentTerms") or s.get("paymentTerms", ""),
        note=str(rev_in.get("notes") or ""),
        logistics_cost=logistics_cost,
        logistics_location=str(rev_in.get("logisticsLocation") or ""),
        cost=totals["cost"], mk_amt=totals["mkAmt"], sub=totals["sub"], vat_amt=totals["vat"],
        total=totals["total"] + logistics_cost,
        created=created, updated=updated,
    )


@router.post("/migrate")
def migrate_legacy(body: dict, user: models.User = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    """Bulk-import quotes from the legacy facade app (localStorage dataset).

    Payload: {projects: [...], settings, rates, gc, acpPanels, hwItems, hwKits, sf, mosqRates, salesPersons}
    Idempotent: quotes whose number already exists are skipped, so re-running a
    migration never duplicates data.
    """
    projects = body.get("projects") or []
    if not isinstance(projects, list) or not projects:
        raise HTTPException(400, "payload.projects must be a non-empty array")
    if len(projects) > 500:
        raise HTTPException(400, "Too many projects (max 500) - split the migration")

    legacy = {k: body.get(k) for k in ("settings", "rates", "gc", "acpPanels", "hwItems", "hwKits", "sf", "mosqRates") if body.get(k)}
    catalog = get_catalog(db)
    sp_by_id = {s.get("id"): s for s in (body.get("salesPersons") or []) if isinstance(s, dict)}
    now = int(time.time() * 1000)

    existing_numbers = {r[0] for r in db.query(models.Quote.number).all()}
    imported, skipped = [], []
    for proj in projects:
        if not isinstance(proj, dict) or not (proj.get("quotes") or []):
            continue
        if len(imported) + len(skipped) >= 2000:
            break
        client = proj.get("client") or {}
        sp = sp_by_id.get(proj.get("salesPersonId")) or {}
        notes_parts = []
        if proj.get("siteAddress"):
            notes_parts.append(f"Site: {proj['siteAddress']}")

        for q_in in proj.get("quotes") or []:
            if not isinstance(q_in, dict):
                continue
            number = str(q_in.get("number") or "").strip()
            if not number:
                continue
            if number in existing_numbers:
                skipped.append(number)
                continue

            first_created = _ms(q_in.get("createdAt"), now)
            revs_in = sorted(
                [r for r in (q_in.get("revisions") or []) if isinstance(r, dict)],
                key=lambda r: int(r.get("rev", 0) or 0),
            )
            sales_person = sp.get("name") or (revs_in[-1].get("createdByName") if revs_in else "") or ""
            desc = str(q_in.get("description") or "").strip()
            if desc:
                notes_parts.append(desc)

            q = models.Quote(
                id=uuid.uuid4().hex[:12],
                number=number,
                project_id=None,
                project_name=str(proj.get("name") or ""),
                client_name=str(client.get("name") or client.get("contact") or ""),
                client_phone=str(client.get("phone") or client.get("compPhone") or ""),
                client_email=str(client.get("email") or client.get("compEmail") or ""),
                sales_person=sales_person,
                notes="\n".join(notes_parts),
                created=first_created,
                updated=now,
            )
            db.add(q)
            for r_in in revs_in:
                rev = _migrate_revision(r_in, q_in, proj, legacy, catalog)
                rev.quote_id = q.id
                db.add(rev)
            existing_numbers.add(number)
            imported.append(number)

    if imported:
        log_action(db, user, "quote.migrated", f"Migrated {len(imported)} quote(s) from legacy facade: {', '.join(imported[:8])}{'...' if len(imported) > 8 else ''}", "📦")
        _notify_admins(db, user, f"{user.name} migrated {len(imported)} quote(s) from the legacy facade app", "success", "📦")
    db.commit()
    return {"ok": True, "imported": len(imported), "skipped": len(skipped),
            "importedNumbers": imported, "skippedNumbers": skipped}


# ---------------------------------------------------------------------------
# Excel export
# ---------------------------------------------------------------------------

def _xlsx_response(data: bytes, filename: str) -> StreamingResponse:
    return StreamingResponse(
        io.BytesIO(data),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/export/all")
def export_all(user: models.User = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    quotes = []
    for q in db.query(models.Quote).order_by(models.Quote.updated.desc()).all():
        quotes.append(_quote_out(q, _quote_revisions(db, q.id)))
    data = excel_export.build_quotes_list_workbook(quotes)
    stamp = _dt.date.today().strftime("%Y%m%d")
    return _xlsx_response(data, f"Interdec-Quotes-{stamp}.xlsx")


@router.get("/{quote_id}/export")
def export_quote(
    quote_id: str,
    rev_id: str | None = None,
    user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    q = _get_quote(db, quote_id)
    revs = _quote_revisions(db, q.id, include_items=True)
    if not revs:
        raise HTTPException(400, "Quote has no revisions to export")
    rev = next((r for r in revs if r["id"] == rev_id), None) if rev_id else None
    rev = rev or max(revs, key=lambda r: r["rev"])
    catalog = get_catalog(db)
    data = excel_export.build_quote_workbook(_quote_out(q), rev, catalog)
    return _xlsx_response(data, f"{q.number}-Rev{rev['rev']}.xlsx")

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
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..database import get_db
from .. import models, auth, pricing, excel_export, pdf_export
from ..activity import log_action, notify_users
from ..files import content_disposition
from .settings import _out as _fx_out, _row as _fx_row
from ..schemas import (
    QuoteCreate, QuoteUpdate, RevisionCreate, RevisionUpdate, StatusUpdate, CatalogUpdate,
)

router = APIRouter(prefix="/api/quotes", tags=["quotes"])

CATALOG_KEYS = {"pdfDesign", "currencies", "products", "subs", "hwItems", "hwKits", "sf", "mosqRates", "acpPanels", "gc", "rates", "settings"}
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


def _fx(db: Session) -> dict:
    return _fx_out(_fx_row(db))["rates"]


def _money(db: Session, currency, fx_rate=None):
    """(code, naira per unit) for a quote. fx_rate=None takes today's rate."""
    code = str(currency or pricing.BASE_CURRENCY).upper().strip()
    if code == pricing.BASE_CURRENCY:
        return code, 1.0
    fx = _fx(db)
    if code not in fx:
        raise HTTPException(400, f"No exchange rate set for {code}. Add it under Import Flow → exchange rates.")
    if fx_rate is not None:
        try:
            rate = float(fx_rate)
        except (TypeError, ValueError):
            raise HTTPException(400, "Exchange rate must be a number")
        if not (rate > 0) or rate > 1e9:
            raise HTTPException(400, "Exchange rate must be greater than zero")
        return code, rate
    return code, round(pricing.ngn_per(code, fx), 6)


def _pc(db: Session, catalog: dict, rate: float = 1.0) -> dict:
    """Catalogue with every price in naira, tagged with the quote's rate."""
    return {**pricing.convert_catalog(catalog, _fx(db), 1.0), "__rate": float(rate or 1.0)}


@router.get("/catalog")
def read_catalog(user: models.User = Depends(auth.require_quotes_access), db: Session = Depends(get_db)):
    overrides = [s.key for s in db.query(models.FacadeSetting).all() if s.key in CATALOG_KEYS]
    fx = _fx(db)
    per = {}
    for code in fx:
        try:
            per[code] = round(pricing.ngn_per(code, fx), 6)
        except ValueError:
            pass
    return {"values": get_catalog(db), "overridden": overrides, "fx": per}


@router.put("/catalog/{key}")
def update_catalog(
    key: str,
    body: CatalogUpdate,
    user: models.User = Depends(auth.require_admin),
    db: Session = Depends(get_db),
):
    if key not in CATALOG_KEYS:
        raise HTTPException(400, f"Unknown catalogue key. Valid: {sorted(CATALOG_KEYS)}")
    _validate_catalog_value(key, body.value, db)
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


SPECIAL_PRODUCTS = {"acp": "ACP Cladding", "balustrade": "Glass Balustrade"}  # priced by their own rules


def _validate_types(key, value, db):
    cat = get_catalog(db)
    if key == "products":
        if not isinstance(value, list) or not value:
            raise HTTPException(400, "products must be a non-empty list")
        ids = [p.get("id") for p in value]
        if any(not i for i in ids) or len(set(ids)) != len(ids):
            raise HTTPException(400, "Every product needs a unique id")
        for p in value:
            if not str(p.get("label") or "").strip():
                raise HTTPException(400, "Every product needs a name")
            if not isinstance(p.get("isLm", False), bool):
                raise HTTPException(400, f"{p['label']}: isLm must be true or false")
        missing = [n for i, n in SPECIAL_PRODUCTS.items() if i in {x["id"] for x in cat["products"]} and i not in ids]
        if missing:
            raise HTTPException(400, f"{missing[0]} is built in and can't be removed (rename it instead)")
    else:  # subs
        if not isinstance(value, dict):
            raise HTTPException(400, "subs must map product id to a list of types")
        prods = {p["id"] for p in cat["products"]}
        seen = set()
        for pid, lst in value.items():
            if pid not in prods:
                continue  # leftovers of a product being removed; harmless
            if not isinstance(lst, list) or not lst:
                raise HTTPException(400, "Every product needs at least one type")
            for st in lst:
                sid, label = st.get("id"), str(st.get("label") or "").strip()
                if not sid or sid in seen:
                    raise HTTPException(400, f"Type ids must be unique ({sid})")
                seen.add(sid)
                if not label:
                    raise HTTPException(400, "Every type needs a name")
                try:
                    kg = float(st.get("kg", 0))
                except (TypeError, ValueError):
                    raise HTTPException(400, f"{label}: aluminium kg/m² must be a number")
                if kg < 0 or kg > 500:
                    raise HTTPException(400, f"{label}: aluminium kg/m² must be between 0 and 500")
                for f in ("mosq", "subframe", "sliding"):
                    if f in st and not isinstance(st[f], bool):
                        raise HTTPException(400, f"{label}: {f} must be true or false")
        for pid in prods:
            if pid not in value:
                raise HTTPException(400, "Every product needs its list of types")


def _validate_catalog_value(key: str, value: dict, db=None):
    """Reject overrides that would crash or silently zero the pricing engine."""
    def num(v, label):
        try:
            f = float(v)
        except (TypeError, ValueError):
            raise HTTPException(400, f"{label} must be a number")
        if f != f or f < 0:
            raise HTTPException(400, f"{label} must be zero or more")
        return f

    if key in ("products", "subs"):
        return _validate_types(key, value, db)
    if key == "hwKits":
        if not isinstance(value, dict):
            raise HTTPException(400, "hwKits must be an object")
        for st, kit in value.items():
            if not isinstance(kit, list):
                raise HTTPException(400, f"Hardware kit for {st} must be a list")
            for k in kit:
                if not k.get("id"):
                    raise HTTPException(400, f"Hardware kit for {st}: every line needs an item")
                q = k.get("q", 0)
                if not isinstance(q, (int, float)) or q < 0 or q > 1000:
                    raise HTTPException(400, f"Hardware kit for {st}: quantities must be 0–1000")
        return
    if key == "pdfDesign":
        msg = pdf_export.validate_design(value)
        if msg:
            raise HTTPException(400, msg)
        return
    if key == "currencies":
        if not isinstance(value, dict):
            raise HTTPException(400, "currencies must be an object")
        return
    if key not in ("acpPanels", "hwItems") and not isinstance(value, dict):
        raise HTTPException(400, f"{key} must be an object")
    if key == "rates":
        br = value.get("brandRates")
        if not isinstance(br, dict) or not br:
            raise HTTPException(400, "rates.brandRates is required")
        for k, v in br.items():
            num(v, f"Brand rate {k}")
        for k in ("gasketRate", "fabRate", "installRate", "subframeRate", "sealantRate"):
            num(value.get(k), k)
        extras = value.get("extras") or []
        if not isinstance(extras, list):
            raise HTTPException(400, "rates.extras must be a list")
        seen = set()
        for ex in extras:
            name = str((ex or {}).get("name") or "").strip()
            if not name:
                raise HTTPException(400, "Every extra charge needs a name")
            if not ex.get("id") or ex["id"] in seen:
                raise HTTPException(400, f"Extra charge '{name}' has a missing or duplicate id")
            seen.add(ex["id"])
            if ex.get("basis") not in pricing.EXTRA_BASES:
                raise HTTPException(400, f"Extra charge '{name}': basis must be one of {sorted(pricing.EXTRA_BASES)}")
            num(ex.get("rate"), f"Extra charge '{name}'")
            if not isinstance(ex.get("products") or [], list):
                raise HTTPException(400, f"Extra charge '{name}': products must be a list")
    elif key == "settings":
        for k in ("defaultMarkup", "minMarkup", "vatRate", "validity"):
            num(value.get(k), k)
        if float(value["defaultMarkup"]) < float(value["minMarkup"]):
            raise HTTPException(400, "Default markup cannot be below the minimum markup")
        if int(float(value["validity"])) < 1:
            raise HTTPException(400, "Quote validity must be at least 1 day")
    elif key == "gc":
        if not isinstance(value.get("types"), list) or not isinstance(value.get("colours"), list) \
                or not isinstance(value.get("basePrices"), dict):
            raise HTTPException(400, "gc needs types, colours and basePrices")
        for k, v in value["basePrices"].items():
            num(v, f"Glass price {k}")
        ids = [t.get("id") for t in value["types"]]
        if not ids or any(not i for i in ids) or len(set(ids)) != len(ids):
            raise HTTPException(400, "Glass types need unique ids")
        for t in value["types"]:
            if not str(t.get("label") or "").strip():
                raise HTTPException(400, "Every glass type needs a name")
        th = value.get("thicknesses") or {}
        for t in ids:
            for size in th.get(t) or []:
                num(value["basePrices"].get(f"{t}__{size}"), f"Glass price {t} {size}")
        cids = [c.get("id") for c in value["colours"]]
        if any(not i for i in cids) or len(set(cids)) != len(cids):
            raise HTTPException(400, "Glass colours need unique ids")
        for c in value["colours"]:
            if not str(c.get("label") or "").strip():
                raise HTTPException(400, "Every glass colour needs a name")
            num(c.get("premium"), f"Colour premium {c.get('label')}")
    elif key in ("acpPanels", "hwItems"):
        what = "ACP panel" if key == "acpPanels" else "Hardware item"
        if not isinstance(value, list):
            raise HTTPException(400, f"{key} must be a list")
        ids = [x.get("id") for x in value]
        if any(not i for i in ids) or len(set(ids)) != len(ids):
            raise HTTPException(400, f"{what}s need unique ids")
        for x in value:
            if not str(x.get("name") or "").strip():
                raise HTTPException(400, f"Every {what.lower()} needs a name")
            num(x.get("p"), f"{what} {x.get('name')}")
    elif key in ("sf", "mosqRates"):
        for k, v in value.items():
            num(v, f"{key}.{k}")


def _calc(items, markup, vat, catalog: dict):
    """Run the pricing engine with every catalogue table (incl. mosquito-net
    rates, which were previously never passed, so nets were always free).

    Pricing always runs in naira at full precision; for a foreign-currency
    quote (catalog["__rate"] = naira per unit) the results are then converted
    to that currency to the cent, so no whole-unit rounding drift creeps in."""
    rate = float(catalog.get("__rate") or 1.0)
    src = items or []
    if rate != 1.0:  # per-item rate overrides are typed in the quote currency
        src = [{**it, "ovGlassRate": float(it["ovGlassRate"]) * rate}
               if isinstance(it, dict) and it.get("ovGlassRate") not in (None, "") else it for it in src]
    out = pricing.calc_totals(
        src, markup, vat,
        rates=catalog.get("rates"), gc=catalog.get("gc"), acp_panels=catalog.get("acpPanels"),
        hw_items=catalog.get("hwItems"), hw_kits=catalog.get("hwKits"), sf=catalog.get("sf"),
        mosq_rates=catalog.get("mosqRates"), products=catalog.get("products"), subs=catalog.get("subs"),
    )
    if rate == 1.0:
        return out
    return pricing.to_currency(out, rate, original_items=items or [])


def _store_items(totals: dict) -> list:
    """Persist item inputs *with* their BOM snapshot, so a saved revision keeps
    showing the figures it was priced with even after the rate card changes."""
    return [dict(it) for it in totals["items"]]


def _float(v, label: str) -> float:
    try:
        f = float(v)
    except (TypeError, ValueError):
        raise HTTPException(400, f"{label} must be a number")
    if f != f or f < 0 or f > 1000:
        raise HTTPException(400, f"{label} must be between 0 and 1000")
    return f


def _settings(catalog: dict) -> dict:
    return catalog.get("settings") or pricing.SETTINGS_DEF


def _clamp_markup(markup, catalog: dict) -> float:
    """Enforce the configurable markup floor server-side (audit hardening)."""
    s = _settings(catalog)
    try:
        m = float(markup)
    except (TypeError, ValueError):
        m = float(s.get("defaultMarkup", 100))
    if m != m:  # NaN
        m = float(s.get("defaultMarkup", 100))
    floor = float(s.get("minMarkup", 70))
    return min(max(m, floor), 1000.0)


# ---------------------------------------------------------------------------
# Stateless calculation (live preview)
# ---------------------------------------------------------------------------

@router.post("/calculate")
def calculate(body: dict, user: models.User = Depends(auth.require_quotes_access), db: Session = Depends(get_db)):
    catalog = get_catalog(db)
    items = body.get("items") or []
    if not isinstance(items, list):
        raise HTTPException(400, "items must be a list")
    s = _settings(catalog)
    markup = body.get("markupPct", s.get("defaultMarkup", 100))
    if markup is None:
        markup = s.get("defaultMarkup", 100)
    markup = _clamp_markup(markup, catalog)
    vat = body.get("vatPct")
    vat = _float(vat, "VAT") if vat is not None else float(s.get("vatRate", 7.5))
    code, rate = _money(db, body.get("currency"), body.get("fxRate"))
    totals = _calc(items, markup, vat, _pc(db, catalog, rate))
    return {"markupPct": markup, "vatPct": vat, "currency": code, "fxRate": rate, **totals}


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
        "statusNote": r.status_note or "",
        "currency": r.currency or "NGN",
        "fxRate": r.fx_rate or 1.0,
        "total": r.total,
        "itemsCount": len(r.items or []),
        "created": r.created,
        "updated": r.updated,
    }
    if include_items:
        items = r.items or []
        if db is not None and items and not all(isinstance(it, dict) and it.get("bom") for it in items):
            # legacy rows stored inputs only: attach a BOM computed from the
            # current catalogue (new rows carry their own priced snapshot)
            items = _calc(items, r.markup_pct, r.vat_pct, _pc(db, get_catalog(db), r.fx_rate or 1.0))["items"]
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
        d["currency"] = latest.get("currency", "NGN") if latest else "NGN"
        d["fxRate"] = latest.get("fxRate", 1.0) if latest else 1.0
        d["totalNgn"] = round((d["total"] or 0) * (d["fxRate"] or 1.0), 2)
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
def list_quotes(user: models.User = Depends(auth.require_quotes_access), db: Session = Depends(get_db)):
    quotes = db.query(models.Quote).order_by(models.Quote.updated.desc()).all()
    out = []
    for q in quotes:
        revs = _quote_revisions(db, q.id)
        out.append(_quote_out(q, revs))
    return out


@router.post("")
def create_quote(
    body: QuoteCreate,
    user: models.User = Depends(auth.require_quotes_access),
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
        if not p:
            raise HTTPException(400, "Linked project not found")
        project_name = p.name

    markup = _clamp_markup(body.markupPct if body.markupPct is not None else s.get("defaultMarkup", 100), catalog)
    vat = _float(body.vatPct, "VAT") if body.vatPct is not None else float(s.get("vatRate", 7.5))

    code, rate = _money(db, body.currency, body.fxRate)
    totals = _calc(body.items, markup, vat, _pc(db, catalog, rate))

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
        items=_store_items(totals),
        markup_pct=markup,
        vat_pct=vat,
        validity_days=int(s.get("validity", 14)),
        payment_terms=s.get("paymentTerms", ""),
        currency=code,
        fx_rate=rate,
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
    try:
        db.commit()
    except IntegrityError:
        # two quotes created at the same instant drew the same number
        db.rollback()
        raise HTTPException(409, "Quote number clash, please save again")
    db.refresh(q)
    return _quote_out(q, _quote_revisions(db, q.id, include_items=True))


@router.get("/{quote_id}")
def get_quote(quote_id: str, user: models.User = Depends(auth.require_quotes_access), db: Session = Depends(get_db)):
    q = _get_quote(db, quote_id)
    return _quote_out(q, _quote_revisions(db, q.id, include_items=True))


@router.put("/{quote_id}")
def update_quote(
    quote_id: str,
    body: QuoteUpdate,
    user: models.User = Depends(auth.require_quotes_access),
    db: Session = Depends(get_db),
):
    q = _get_quote(db, quote_id)
    data = body.model_dump(exclude_none=True)
    if "projectId" in data:
        pid = data["projectId"] or None
        p = db.query(models.Project).filter(models.Project.id == pid).first() if pid else None
        if pid and not p:
            raise HTTPException(400, "Linked project not found")
        q.project_id = pid  # was never saved before: only the name snapshot changed
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
    totals = _calc(rev.items or [], rev.markup_pct, rev.vat_pct, _pc(db, get_catalog(db), rev.fx_rate or 1.0))
    rev.items = _store_items(totals)
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
    user: models.User = Depends(auth.require_quotes_access),
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
    vat = _float(body.vatPct, "VAT") if body.vatPct is not None else (latest.vat_pct if latest else float(s.get("vatRate", 7.5)))
    prev_code = (latest.currency or "NGN") if latest else "NGN"
    want = (body.currency or prev_code).upper()
    keep_rate = body.fxRate if body.fxRate is not None else ((latest.fx_rate or 1.0) if latest and want == prev_code else None)
    code, rate = _money(db, want, keep_rate)

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
        logistics_cost=(latest.logistics_cost or 0.0) if latest else 0.0,
        logistics_location=(latest.logistics_location or "") if latest else "",
        currency=code,
        fx_rate=rate,
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
    user: models.User = Depends(auth.require_quotes_access),
    db: Session = Depends(get_db),
):
    q = _get_quote(db, quote_id)
    rev = db.query(models.QuoteRevision).filter(models.QuoteRevision.id == rev_id, models.QuoteRevision.quote_id == quote_id).first()
    if not rev:
        raise HTTPException(404, "Revision not found")
    if rev.status != "draft":
        raise HTTPException(400, f"Rev.{rev.rev} is {rev.status}; create a new revision to change it")

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
        rev.vat_pct = _float(data["vatPct"], "VAT")
        changed = True
    if "currency" in data or "fxRate" in data:
        code = (data.get("currency") or rev.currency or "NGN").upper()
        same = code == (rev.currency or "NGN")
        rate_in = data.get("fxRate", rev.fx_rate if same else None)
        code, rate = _money(db, code, rate_in)
        if code != (rev.currency or "NGN") or rate != (rev.fx_rate or 1.0):
            rev.currency, rev.fx_rate = code, rate
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
    user: models.User = Depends(auth.require_quotes_access),
    db: Session = Depends(get_db),
):
    q = _get_quote(db, quote_id)
    rev = db.query(models.QuoteRevision).filter(models.QuoteRevision.id == rev_id, models.QuoteRevision.quote_id == quote_id).first()
    if not rev:
        raise HTTPException(404, "Revision not found")
    if body.status not in STATUSES:
        raise HTTPException(400, "Status must be one of: draft, sent, won, lost")
    latest_rev = (
        db.query(models.QuoteRevision.rev)
        .filter(models.QuoteRevision.quote_id == quote_id)
        .order_by(models.QuoteRevision.rev.desc())
        .first()
    )
    if latest_rev and rev.rev != latest_rev[0] and body.status != rev.status:
        raise HTTPException(400, "Only the latest revision's status can change; older revisions are history")
    note = (body.note or "").strip()[:500]
    if body.status in ("won", "lost") and not note:
        raise HTTPException(400, "Add a reason or PO reference when marking a quote won or lost")
    old = rev.status
    project_msg = ""
    if body.status == "won" and body.project:
        mode = (body.project or {}).get("mode")
        if mode == "create":
            name = str(body.project.get("name") or "").strip()[:120] or (q.client_name or q.number)
            p = models.Project(id=uuid.uuid4().hex[:12], name=name, client=q.client_name or "",
                               description=f"Created from quote {q.number} (won{': ' + note if note else ''})",
                               status="Active", created=int(time.time() * 1000))
            db.add(p)
            q.project_id, q.project_name = p.id, p.name
            log_action(db, user, "project.created", f"Created project {p.name} from won quote {q.number}", "📁")
            project_msg = f" · project {p.name} created"
        elif mode == "link":
            p = db.query(models.Project).filter(models.Project.id == body.project.get("projectId")).first()
            if not p:
                raise HTTPException(400, "Project to link not found")
            q.project_id, q.project_name = p.id, p.name
            if p.status == "On Hold":
                p.status = "Active"
            project_msg = f" · linked to {p.name}"
        elif mode not in (None, "", "none"):
            raise HTTPException(400, "project.mode must be create, link or none")
    rev.status = body.status
    rev.status_note = note if body.status in ("won", "lost") else ""
    rev.updated = int(time.time() * 1000)
    q.updated = rev.updated
    label = {"draft": "Draft", "sent": "Sent", "won": "Won", "lost": "Lost"}[body.status]
    detail = f"{q.number} Rev.{rev.rev}: {old} -> {body.status}" + (f" ({note})" if note else "") + project_msg
    log_action(db, user, "quote.status", detail, "🔁")
    if body.status in ("sent", "won", "lost"):
        msg = f"{q.number} Rev.{rev.rev} marked {label} ({user.name})" + (f": {note}" if note else "")
        _notify_admins(db, user, msg, "success" if body.status == "won" else "info", "🧾")
    db.commit()
    if body.status in ("won", "lost") and old != body.status:
        try:
            from .. import notify_mail
            notify_mail.quote_outcome(db, q, rev, user)
            db.commit()
        except Exception:  # email must never break saving
            db.rollback()
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
    items = [{k: v for k, v in it.items() if k != "bom"} for it in items if isinstance(it, dict)]

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
    items = [it for it in items if isinstance(it, dict)]
    try:
        rev_no = int(rev_in.get("rev", 0))
    except (TypeError, ValueError):
        rev_no = 0

    try:
        logistics_cost = max(0.0, float(rev_in.get("logisticsCost") or 0)) if rev_in.get("outsideLagos") else 0.0
    except (TypeError, ValueError):
        logistics_cost = 0.0
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
        items=_store_items(totals),
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
def migrate_legacy(body: dict, user: models.User = Depends(auth.require_quotes_access), db: Session = Depends(get_db)):
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
        if not isinstance(client, dict):
            client = {}
        sp = sp_by_id.get(proj.get("salesPersonId")) or {}
        site = f"Site: {proj['siteAddress']}" if proj.get("siteAddress") else ""

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
            def _rev_no(r):
                try:
                    return int(r.get("rev", 0) or 0)
                except (TypeError, ValueError):
                    return 0

            revs_in = sorted(
                [r for r in (q_in.get("revisions") or []) if isinstance(r, dict)],
                key=_rev_no,
            )
            if not revs_in:
                skipped.append(number)
                continue
            sales_person = sp.get("name") or (revs_in[-1].get("createdByName") if revs_in else "") or ""
            # notes are per quote (they used to accumulate across a project's quotes)
            notes_parts = [p for p in (site, str(q_in.get("description") or "").strip()) if p]

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
        headers={"Content-Disposition": content_disposition("attachment", filename)},
    )


@router.get("/export/all")
def export_all(user: models.User = Depends(auth.require_quotes_access), db: Session = Depends(get_db)):
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
    internal: bool = False,
    user: models.User = Depends(auth.require_quotes_access),
    db: Session = Depends(get_db),
):
    q = _get_quote(db, quote_id)
    revs = _quote_revisions(db, q.id, include_items=True)
    if not revs:
        raise HTTPException(400, "Quote has no revisions to export")
    rev = next((r for r in revs if r["id"] == rev_id), None) if rev_id else None
    rev = rev or max(revs, key=lambda r: r["rev"])
    catalog = get_catalog(db)
    if internal and not auth.is_quote_admin(user):
        raise HTTPException(403, "Only quote admins can export internal costs")
    data = excel_export.build_quote_workbook(_quote_out(q), rev, catalog, internal=internal)
    suffix = "-INTERNAL" if internal else ""
    return _xlsx_response(data, f"{q.number}-Rev{rev['rev']}{suffix}.xlsx")



# ---------------------------------------------------------------------------
# PDF (WeasyPrint) — client document styled by the PDF Design settings
# ---------------------------------------------------------------------------

def _pdf_response(data: bytes, filename: str, inline: bool = False):
    disp = content_disposition("inline" if inline else "attachment", filename)
    return StreamingResponse(io.BytesIO(data), media_type="application/pdf", headers={"Content-Disposition": disp})


def _render_pdf(quote: dict, rev: dict, catalog: dict, design: dict) -> bytes:
    try:
        return pdf_export.render_pdf(quote, rev, _settings(catalog), design)
    except pdf_export.PdfUnavailable as e:
        raise HTTPException(503, str(e))


@router.get("/{quote_id}/pdf")
def quote_pdf(
    quote_id: str,
    rev_id: str | None = None,
    inline: bool = False,
    user: models.User = Depends(auth.require_quotes_access),
    db: Session = Depends(get_db),
):
    q = _get_quote(db, quote_id)
    revs = _quote_revisions(db, q.id, include_items=True)
    if not revs:
        raise HTTPException(400, "Quote has no revisions to export")
    rev = next((r for r in revs if r["id"] == rev_id), None) if rev_id else None
    rev = rev or max(revs, key=lambda r: r["rev"])
    catalog = get_catalog(db)
    data = _render_pdf(_quote_out(q), rev, catalog, catalog.get("pdfDesign") or {})
    return _pdf_response(data, f"{q.number}-Rev{rev['rev']}.pdf", inline)


def _sample_quote(db: Session, catalog: dict):
    """Latest real quote if there is one, otherwise a made-up two-item quote."""
    latest = db.query(models.Quote).order_by(models.Quote.updated.desc()).first()
    if latest:
        revs = _quote_revisions(db, latest.id, include_items=True)
        if revs:
            return _quote_out(latest), max(revs, key=lambda r: r["rev"])
    s = _settings(catalog)
    items = [
        {"id": "s1", "product": "et_window", "subTypeId": "etw_s2", "width": 2400, "height": 1500, "qty": 4,
         "glassTypeId": "tempered", "glassThickness": "8mm", "glassColour": "clear", "position": "W1", "hasMosq": True},
        {"id": "s2", "product": "et_door", "subTypeId": "etd_single", "width": 1000, "height": 2400, "qty": 2,
         "glassTypeId": "laminated", "glassThickness": "10.38mm (5+5)", "glassColour": "grey", "position": "D1"},
    ]
    t = _calc(items, s.get("defaultMarkup", 100), s.get("vatRate", 7.5), _pc(db, catalog, 1.0))
    now = int(time.time() * 1000)
    quote = {"number": "IDF-SAMPLE-001", "clientName": "Sample Client Ltd", "clientPhone": "+234 800 000 0000",
             "clientEmail": "client@example.com", "salesPerson": "Sales Person", "projectName": "Sample Project"}
    rev = {"rev": 0, "items": t["items"], "markupPct": s.get("defaultMarkup", 100), "vatPct": s.get("vatRate", 7.5),
           "sub": t["sub"], "vatAmt": t["vat"], "total": t["total"], "currency": "NGN", "created": now,
           "validityDays": s.get("validity", 14), "paymentTerms": s.get("paymentTerms", "")}
    return quote, rev


@router.post("/pdf/preview")
def pdf_preview(body: dict, user: models.User = Depends(auth.require_admin), db: Session = Depends(get_db)):
    """Render an unsaved design against a real (or sample) quote for the PDF Design page."""
    design = body.get("design") or {}
    msg = pdf_export.validate_design(design)
    if msg:
        raise HTTPException(400, msg)
    catalog = get_catalog(db)
    quote, rev = _sample_quote(db, catalog)
    data = _render_pdf(quote, rev, catalog, design)
    return _pdf_response(data, "preview.pdf", inline=True)


@router.get("/pdf/defaults")
def pdf_defaults(user: models.User = Depends(auth.require_quotes_access)):
    return {"design": pdf_export.DEFAULT_DESIGN, "fonts": list(pdf_export.FONTS), "layouts": list(pdf_export.LAYOUTS),
            "papers": list(pdf_export.PAPERS)}

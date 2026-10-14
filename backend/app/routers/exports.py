"""ImportFlow downloads: every list, record and report as PDF or Excel.

GET /api/importflow/export/{kind}?format=pdf|xlsx[&id=…][&type=…][&status=…&company=…&q=…]

kinds: dashboard, shipments, shipment, projects, project, vendors, shippers, agents,
report (type = status | project | company | vendor | shipper | costs | all)

The document look comes from the ImportFlow "Document Design" settings
(GET/PUT /api/importflow/design), independent of the quotation PDF design.
"""
import io
import time
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ..database import get_db
from .. import models, auth, doc_export, finance
from ..activity import log_action
from ..files import content_disposition
from ..pdf_export import PdfUnavailable
from .settings import _out as _fx_out, _row as _fx_row

router = APIRouter(prefix="/api/importflow", tags=["importflow-export"])

DESIGN_KEY = "ifDocDesign"
STATUS_LABELS = {"order_placed": "Order Placed", "under_production": "Under Production",
                 "in_transit": "In Transit", "completed": "Completed"}
STATUS_COLORS = {"order_placed": "#3b82f6", "under_production": "#f59e0b", "in_transit": "#8b5cf6", "completed": "#10b981"}
STATUS_ORDER = list(STATUS_LABELS)
COMPANIES = {"facade": ("Facade", "#5B8EC9"), "davinci": ("Davinci", "#D4684A"), "doortec": ("Doortec", "#5BBF3A")}
TIMELINE = [("created", "Order placed"), ("invoiceUploaded", "Vendor invoice uploaded"),
            ("packingReady", "Packing list ready"), ("shipperSelected", "Shipper assigned"),
            ("shipped", "Shipped"), ("shipperInvoiced", "Shipper invoice uploaded"), ("closed", "Goods received")]
USD = {"label": "Value (USD)", "align": "right", "num": True, "prefix": "$ "}


# ---------------------------------------------------------------------------
# design settings
# ---------------------------------------------------------------------------

def _design_row(db):
    return db.query(models.FacadeSetting).filter(models.FacadeSetting.key == DESIGN_KEY).first()


def _design(db) -> dict:
    row = _design_row(db)
    return (row.value if row else None) or {}


def _require_if_admin(user: models.User = Depends(auth.get_current_user)) -> models.User:
    if auth.importflow_role(user) != "admin":
        raise HTTPException(403, "Only ImportFlow admins can change the document design")
    return user


@router.get("/design")
def get_design(user: models.User = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    return {"design": doc_export.merged_design(_design(db)), "defaults": doc_export.DEFAULT_DESIGN}


@router.put("/design")
def put_design(body: dict, user: models.User = Depends(_require_if_admin), db: Session = Depends(get_db)):
    value = body.get("design")
    msg = doc_export.validate_design(value if isinstance(value, dict) else None)
    if msg:
        raise HTTPException(400, msg)
    row = _design_row(db)
    now = int(time.time() * 1000)
    if row:
        row.value, row.updated = value, now
    else:
        db.add(models.FacadeSetting(key=DESIGN_KEY, value=value, updated=now))
    log_action(db, user, "importflow.design", "Updated the ImportFlow document design", "🎨")
    db.commit()
    return {"design": doc_export.merged_design(value)}


@router.post("/design/preview")
def preview_design(body: dict, user: models.User = Depends(_require_if_admin), db: Session = Depends(get_db)):
    design = body.get("design") or {}
    msg = doc_export.validate_design(design)
    if msg:
        raise HTTPException(400, msg)
    kind = body.get("kind") or "report"
    params = {"type": "status"} if kind == "report" else {}
    doc = _build(db, kind, params)
    return _respond(doc, design, "pdf", "preview", user, inline=True)


# ---------------------------------------------------------------------------
# data helpers
# ---------------------------------------------------------------------------

class _Ctx:
    def __init__(self, db: Session):
        self.db = db
        fx = _fx_out(_fx_row(db))
        self.rates = fx["rates"]
        self.fx_date = fx.get("updated") or 0
        self.vendors = {v.id: v for v in db.query(models.Vendor).all()}
        self.shippers = {s.id: s for s in db.query(models.Shipper).all()}
        self.agents = {a.id: a for a in db.query(models.ClearingAgent).all()}
        self.projects = {p.id: p for p in db.query(models.Project).all()}
        self.shipments = db.query(models.Shipment).order_by(models.Shipment.created.desc()).all()
        self._money = finance.Money(db)
        self._budgets = {}

    def budget(self, proj):
        if proj.id not in self._budgets:
            self._budgets[proj.id] = finance.project_budget(
                self.db, proj, self._money, shipments=[s for s in self.shipments if s.project_id == proj.id])
        return self._budgets[proj.id]

    def usd(self, s) -> float:
        return round(float(s.value or 0) * float(self.rates.get((s.currency or "USD").upper(), 1) or 1), 2)

    def cost_usd(self, c) -> float:
        if not c:
            return 0.0
        return round(float(c.get("total") or 0) * float(self.rates.get((c.get("currency") or "USD").upper(), 1) or 1), 2)

    def landed(self, s) -> float:
        return round(self.usd(s) + self.cost_usd(s.shipping_cost) + self.cost_usd(s.clearing_cost), 2)

    def total(self, lst) -> float:
        return round(sum(self.usd(s) for s in lst), 2)

    def vendor(self, sid):
        v = self.vendors.get(sid)
        return v.name if v else ""

    def shipper(self, sid):
        v = self.shippers.get(sid)
        return v.name if v else ""

    def project(self, pid):
        p = self.projects.get(pid)
        return p.name if p else "General stock"

    def fx_note(self):
        parts = [f"{k} = {v:g} USD" for k, v in sorted(self.rates.items()) if k != "USD"]
        when = datetime.fromtimestamp(self.fx_date / 1000).strftime("%d %b %Y") if self.fx_date else "default rates"
        return f"Values converted to USD using exchange rates from {when}: " + ", ".join(parts)


def _company(cid):
    return COMPANIES.get(cid, (cid or "", "#64748b"))[0]


def _date(ms):
    try:
        return datetime.fromtimestamp(int(ms) / 1000).strftime("%d %b %Y") if ms else ""
    except (TypeError, ValueError, OSError):
        return ""


def _eta(v):
    if not v:
        return ""
    try:
        return datetime.fromisoformat(str(v)[:10]).strftime("%d %b %Y")
    except ValueError:
        return str(v)


def _money(n):
    return f"$ {n:,.0f}"


def _value_text(s):
    return f"{(s.currency or 'USD')} {float(s.value or 0):,.2f}"


def _status_cards(ctx, lst):
    return [{"label": STATUS_LABELS[st], "value": str(len([s for s in lst if s.status == st])),
             "sub": _money(ctx.total([s for s in lst if s.status == st])), "color": STATUS_COLORS[st]}
            for st in STATUS_ORDER]


SHIP_COLS = [{"label": "Ref"}, {"label": "Company"}, {"label": "Description"}, {"label": "Vendor"},
             {"label": "Project"}, {"label": "Status"}, {"label": "ETA"}, {"label": "Value"}, USD]


def _ship_row(ctx, s):
    return [s.ref, _company(s.company_id), s.description or "", ctx.vendor(s.vendor_id), ctx.project(s.project_id),
            STATUS_LABELS.get(s.status, s.status), _eta(s.eta), _value_text(s), ctx.usd(s)]


def _ship_table(ctx, lst, heading=None, note=None, color=None, cols=None, row=None):
    cols = cols or SHIP_COLS
    rows = [(row or _ship_row)(ctx, s) for s in lst]
    total = [""] * len(cols)
    total[0], total[-1] = f"{len(lst)} shipment{'s' if len(lst) != 1 else ''}", ctx.total(lst)
    return {"heading": heading, "note": note, "color": color, "columns": cols, "rows": rows, "total": total,
            "empty": "No shipments."}


def _filter(ctx, params):
    lst = ctx.shipments
    if params.get("status") not in (None, "", "All"):
        lst = [s for s in lst if s.status == params["status"]]
    if params.get("company") not in (None, "", "All"):
        lst = [s for s in lst if s.company_id == params["company"]]
    q = (params.get("q") or "").strip().lower()
    if q:
        lst = [s for s in lst if q in " ".join([s.ref or "", s.description or "", ctx.vendor(s.vendor_id),
                                                   ctx.project(s.project_id)]).lower()]
    return lst


# ---------------------------------------------------------------------------
# documents
# ---------------------------------------------------------------------------

def _doc_shipments(ctx, p):
    lst = _filter(ctx, p)
    bits = []
    if p.get("status") not in (None, "", "All"):
        bits.append(STATUS_LABELS.get(p["status"], p["status"]))
    if p.get("company") not in (None, "", "All"):
        bits.append(_company(p["company"]))
    if p.get("q"):
        bits.append(f'matching "{p["q"]}"')
    sub = f"{len(lst)} shipments · {_money(ctx.total(lst))}" + (f" · filtered: {', '.join(bits)}" if bits else "")
    return {"title": "Shipments", "subtitle": sub, "landscape": True, "summary": _status_cards(ctx, lst),
            "sections": [_ship_table(ctx, lst)], "notes": [ctx.fx_note()]}


def _doc_shipment(ctx, p):
    s = next((x for x in ctx.shipments if x.id == p.get("id")), None)
    if not s:
        raise HTTPException(404, "Shipment not found")
    v = ctx.vendors.get(s.vendor_id)
    sp = ctx.shippers.get(s.shipper_id)
    dates = s.dates or {}
    docs = [[label, (f or {}).get("name") or "Not uploaded", _date((f or {}).get("uploaded"))]
            for label, f in (("Vendor invoice", s.vendor_invoice), ("Packing list", s.packing_list),
                             ("Shipper invoice", s.shipper_invoice))]
    return {
        "title": f"Shipment {s.ref}", "subtitle": s.description or "",
        "summary": [{"label": "Status", "value": STATUS_LABELS.get(s.status, s.status), "color": STATUS_COLORS.get(s.status)},
                    {"label": "Value", "value": _value_text(s), "sub": f"≈ {_money(ctx.usd(s))}"},
                    {"label": "ETA", "value": _eta(s.eta) or "Not set"},
                    {"label": "Landed cost", "value": _money(ctx.landed(s)), "sub": "goods + shipping + clearing"}],
        "sections": [
            {"heading": "Details", "kv": [
                ["Reference", s.ref], ["Company", _company(s.company_id)], ["Project", ctx.project(s.project_id)],
                ["Category", s.category], ["Production time", s.production_days], ["Payment terms", s.payment_terms],
                ["Shipping method", s.ship_method], ["Goods received", "Yes" if s.goods_confirmed else "No"],
                ["Created", _date(s.created)]]},
            {"heading": "Vendor", "kv": [["Name", v.name if v else ""], ["Contact", v.contact if v else ""],
                                          ["Email", v.email if v else ""], ["Phone", v.phone if v else ""],
                                          ["Country", v.country if v else ""]]},
            {"heading": "Shipper", "kv": [["Name", sp.name if sp else "Not assigned"], ["Contact", sp.contact if sp else ""],
                                           ["Email", sp.email if sp else ""], ["Phone", sp.phone if sp else ""]]},
            {"heading": "Timeline", "columns": [{"label": "Step"}, {"label": "Date"}],
             "rows": [[label, _date(dates.get(k)) or "—"] for k, label in TIMELINE]},
            {"heading": "Documents", "columns": [{"label": "Document"}, {"label": "File"}, {"label": "Uploaded"}], "rows": docs},
        ] + [_vendor_pay_section(s)] + _cost_sections(ctx, s),
        "notes": [ctx.fx_note()],
    }


def _cost_lines(c, heading, extra_kv):
    cur = (c or {}).get("currency") or ""
    num = {"label": f"Amount ({cur})" if cur else "Amount", "align": "right", "num": True, "decimals": 2}
    paid = "Paid" + (f" on {_eta(c.get('paidOn'))}" if c.get("paidOn") else "") if (c or {}).get("paid") else "Not paid"
    return {"heading": heading, "kv": extra_kv + [["Invoice / reference", (c or {}).get("invoiceRef")], ["Payment", paid],
                                                   ["Note", (c or {}).get("note")]],
            "columns": [{"label": "Charge"}, num], "rows": [[l.get("label"), float(l.get("amount") or 0)] for l in (c or {}).get("lines") or []],
            "total": ["Total", float((c or {}).get("total") or 0)], "empty": "Not recorded yet."}


def _vendor_pay_section(s):
    cur = s.currency or "USD"
    st = {"paid": "Fully paid", "part": "Part paid", "unpaid": "Not paid", "n/a": "No order value"}[finance.vendor_status(s)]
    num = {"label": f"Amount ({cur})", "align": "right", "num": True, "decimals": 2}
    return {"heading": "Vendor payments",
            "note": f"{st} · paid {cur} {finance.vendor_paid(s):,.2f} of {cur} {float(s.value or 0):,.2f} · still owed {cur} {finance.vendor_balance(s):,.2f}"
                    + (f" · terms: {s.payment_terms}" if s.payment_terms else "") + (" · PAYMENT DUE" if finance.payment_due(s) else ""),
            "columns": [{"label": "Date"}, {"label": "Payment"}, {"label": "Reference"}, num],
            "rows": [[_eta(p.get("date")), p.get("kind"), p.get("ref") or "", float(p.get("amount") or 0)] for p in (s.vendor_payments or [])],
            "total": ["", "", "Paid", finance.vendor_paid(s)], "empty": "No payments recorded."}


def _cost_sections(ctx, s):
    if s.status not in ("in_transit", "completed") and not (s.shipping_cost or s.clearing_cost):
        return []
    a = ctx.agents.get(s.clearing_agent_id)
    sh = _cost_lines(s.shipping_cost, "Shipping cost", [["Shipper", ctx.shipper(s.shipper_id) or "Not assigned"]])
    cl = _cost_lines(s.clearing_cost, "Clearing", [["Clearing agent", a.name if a else "Not chosen"],
                                                  ["Agent contact", " · ".join(x for x in [a.contact, a.phone, a.email] if x) if a else ""]])
    docs = (s.clearing_cost or {}).get("docs") or []
    if docs:
        cl["note"] = "Documents: " + ", ".join(f"{d.get('label') + ': ' if d.get('label') else ''}{d.get('name')}" for d in docs)
    landed = {"heading": "Landed cost (USD)", "columns": [{"label": "Item"}, {**USD, "label": "USD", "decimals": 2}],
              "rows": [["Goods", ctx.usd(s)], ["Shipping", ctx.cost_usd(s.shipping_cost)], ["Clearing", ctx.cost_usd(s.clearing_cost)]],
              "total": ["Landed cost", ctx.landed(s)]}
    return [sh, cl, landed]


def _doc_projects(ctx, p):
    projs = sorted(ctx.projects.values(), key=lambda x: -(x.created or 0))
    if p.get("status") not in (None, "", "All"):
        projs = [x for x in projs if x.status == p["status"]]
    q = (p.get("q") or "").strip().lower()
    if q:
        projs = [x for x in projs if q in f"{x.name} {x.client}".lower()]
    rows = []
    for x in projs:
        lst = [s for s in ctx.shipments if s.project_id == x.id]
        active = len([s for s in lst if s.status != "completed"])
        b = ctx.budget(x)
        rows.append([x.name, x.client or "", x.status, len(lst), active, ctx.total(lst), b["contract"], b["spent"], b["margin"],
                     f"{b['marginPct']}%" if b["marginPct"] is not None else "—"])
    cols = [{"label": "Project"}, {"label": "Client"}, {"label": "Status"},
            {"label": "Shipments", "align": "right", "num": True}, {"label": "Active", "align": "right", "num": True},
            USD, {"label": "Contract", "align": "right", "num": True, "prefix": "₦ "}, {"label": "Spent", "align": "right", "num": True, "prefix": "₦ "}, {"label": "Margin", "align": "right", "num": True, "prefix": "₦ "}, {"label": "Margin %", "align": "right"}]
    tsum = lambda i: round(sum(r[i] for r in rows), 2)
    total = [f"{len(rows)} projects", "", "", tsum(3), tsum(4), tsum(5), tsum(6), tsum(7), tsum(8), ""]
    counts = {st: len([x for x in projs if x.status == st]) for st in ("Active", "On Hold", "Completed")}
    return {"title": "Projects", "subtitle": f"{len(rows)} projects", "landscape": True,
            "summary": [{"label": k, "value": str(v)} for k, v in counts.items()],
            "sections": [{"columns": cols, "rows": rows, "total": total, "empty": "No projects."}],
            "notes": [ctx.fx_note()]}


def _doc_project(ctx, p):
    x = ctx.projects.get(p.get("id"))
    if not x:
        raise HTTPException(404, "Project not found")
    lst = [s for s in ctx.shipments if s.project_id == x.id]
    cols = [c for c in SHIP_COLS if c["label"] != "Project"]
    row = lambda c, s: [v for i, v in enumerate(_ship_row(c, s)) if i != 4]
    return {"title": x.name, "subtitle": f"Client: {x.client or '—'} · {x.status}", "landscape": True,
            "summary": _status_cards(ctx, lst),
            "sections": [{"heading": "Project", "kv": [["Client", x.client], ["Status", x.status], ["Created", _date(x.created)],
                                                       ["Shipments", str(len(lst))], ["Total value", _money(ctx.total(lst))]]},
                         _budget_section(ctx.budget(x)),
                         {**_ship_table(ctx, lst, cols=cols, row=row), "heading": "Shipments"}]
            + ([{"heading": "Description", "kv": [["Notes", x.description]]}] if x.description else []),
            "notes": [ctx.fx_note()]}


def _ngn(n):
    return f"₦ {n:,.0f}"


def _budget_section(b):
    rows = [["Contract value (won quotes, excl. VAT)", b["contract"]], ["Goods (vendor orders)", b["goods"]],
            ["Shipping", b["shipping"]], ["Clearing", b["clearing"]], ["Spent on imports (landed)", b["spent"]],
            ["Margin so far", b["margin"]], ["Paid to vendors", b["vendorPaid"]], ["Still owed to vendors", b["vendorOwed"]]]
    if b["estimatedCost"]:
        rows.append(["Quoted cost (incl. fabrication & install)", b["estimatedCost"]])
    note = (f"{b['usedPct']}% of the contract spent · margin {b['marginPct']}%" if b["contract"]
            else "No won quote linked yet, so there's no contract value to compare against.")
    if b["wonQuotes"]:
        note += " · quotes: " + ", ".join(q["number"] for q in b["wonQuotes"])
    return {"heading": "Budget vs actual (₦)", "note": note, "columns": [{"label": "Item"}, {"label": "Naira", "align": "right", "num": True, "prefix": "₦ "}],
            "rows": rows}


def _doc_partners(ctx, p, kind):
    pool = {"vendors": ctx.vendors, "shippers": ctx.shippers, "agents": ctx.agents}[kind]
    items = sorted(pool.values(), key=lambda x: (x.name or "").lower())
    if p.get("category") not in (None, "", "All"):
        items = [x for x in items if x.category == p["category"]]
    q = (p.get("q") or "").strip().lower()
    if q:
        items = [x for x in items if q in f"{x.name} {x.contact} {x.country}".lower()]
    key = {"vendors": "vendor_id", "shippers": "shipper_id", "agents": "clearing_agent_id"}[kind]
    rows = []
    for x in items:
        lst = [s for s in ctx.shipments if getattr(s, key) == x.id]
        value = round(sum(ctx.cost_usd(s.clearing_cost) for s in lst), 2) if kind == "agents" else ctx.total(lst)
        r = [x.name, x.category or "", x.country or "", x.contact or "", x.email or "", x.phone or "", len(lst), value]
        if kind == "vendors":
            r.insert(6, len(x.catalogs or []))
        rows.append(r)
    cols = [{"label": "Name"}, {"label": "Category"}, {"label": "Country"}, {"label": "Contact"}, {"label": "Email"},
            {"label": "Phone"}]
    if kind == "vendors":
        cols.append({"label": "Catalogues", "align": "right", "num": True})
    cols += [{"label": "Shipments", "align": "right", "num": True},
             {**USD, "label": "Clearing billed (USD)"} if kind == "agents" else USD]
    noun = "clearing agents" if kind == "agents" else kind
    total = [f"{len(rows)} {noun}"] + [""] * (len(cols) - 3) + [sum(r[-2] for r in rows), round(sum(r[-1] for r in rows), 2)]
    return {"title": noun.capitalize(), "subtitle": f"{len(rows)} {noun}", "landscape": True,
            "sections": [{"columns": cols, "rows": rows, "total": total, "empty": f"No {noun}."}],
            "notes": [ctx.fx_note()]}


def _doc_dashboard(ctx, p):
    lst = ctx.shipments
    active = [s for s in lst if s.status != "completed"]
    upcoming = sorted([s for s in active if s.eta], key=lambda s: str(s.eta))[:15]
    by_company = []
    for cid, (name, color) in COMPANIES.items():
        cl = [s for s in lst if s.company_id == cid]
        by_company.append([name, len(cl), len([s for s in cl if s.status != "completed"]), ctx.total(cl)])
    return {"title": "ImportFlow overview", "subtitle": f"{len(active)} active of {len(lst)} shipments · pipeline {_money(ctx.total(active))}",
            "summary": _status_cards(ctx, lst), "landscape": True,
            "sections": [
                _ship_table(ctx, upcoming, heading="Next arrivals", note="Active shipments with an ETA, soonest first"),
                {"heading": "By company", "columns": [{"label": "Company"}, {"label": "Shipments", "align": "right", "num": True},
                                                       {"label": "Active", "align": "right", "num": True}, USD],
                 "rows": by_company},
            ], "notes": [ctx.fx_note()]}


def _report(ctx, rtype):
    lst = ctx.shipments
    secs = []
    if rtype == "status":
        for st in STATUS_ORDER:
            g = [s for s in lst if s.status == st]
            if g:
                secs.append(_ship_table(ctx, g, heading=f"{STATUS_LABELS[st]} ({len(g)})", color=STATUS_COLORS[st],
                                        note=_money(ctx.total(g))))
        title, cards = "Shipments by Status", _status_cards(ctx, lst)
    elif rtype == "project":
        for x in sorted(ctx.projects.values(), key=lambda x: x.name.lower()):
            g = [s for s in lst if s.project_id == x.id]
            if g:
                secs.append(_ship_table(ctx, g, heading=x.name, note=f"{x.client or '—'} · {_money(ctx.total(g))} · {len(g)} shipments"))
        g = [s for s in lst if not s.project_id]
        if g:
            secs.append(_ship_table(ctx, g, heading="General stock", note=f"{_money(ctx.total(g))} · {len(g)} shipments"))
        title, cards = "Shipments by Project", None
    elif rtype == "company":
        cards = []
        for cid, (name, color) in COMPANIES.items():
            g = [s for s in lst if s.company_id == cid]
            cards.append({"label": name, "value": str(len(g)), "sub": _money(ctx.total(g)), "color": color})
            if g:
                act = len([s for s in g if s.status != "completed"])
                secs.append(_ship_table(ctx, g, heading=name, color=color, note=f"{_money(ctx.total(g))} · {len(g)} shipments ({act} active)"))
        title = "Shipments by Company"
    elif rtype == "vendor":
        for v in sorted(ctx.vendors.values(), key=lambda x: x.name.lower()):
            g = [s for s in lst if s.vendor_id == v.id]
            if g:
                secs.append(_ship_table(ctx, g, heading=v.name, note=f"{v.country or '—'} · {v.category or '—'} · {_money(ctx.total(g))} · {len(g)} shipments"))
        title, cards = "Shipments by Vendor", None
    elif rtype == "shipper":
        cols = [{"label": "Ref"}, {"label": "Company"}, {"label": "Description"}, {"label": "Method"},
                {"label": "ETA"}, {"label": "Status"}, {"label": "Value"}, USD]
        row = lambda c, s: [s.ref, _company(s.company_id), s.description or "", s.ship_method or "", _eta(s.eta),
                            STATUS_LABELS.get(s.status, s.status), _value_text(s), c.usd(s)]
        for sp in sorted(ctx.shippers.values(), key=lambda x: x.name.lower()):
            g = [s for s in lst if s.shipper_id == sp.id]
            if g:
                secs.append(_ship_table(ctx, g, heading=sp.name, cols=cols, row=row,
                                        note=f"{sp.country or '—'} · {sp.category or '—'} · {_money(ctx.total(g))} · {len(g)} shipments"))
        title, cards = "Shipments by Shipper", None
    elif rtype == "budget":
        projs = sorted(ctx.projects.values(), key=lambda x: x.name.lower())
        rows = []
        for x in projs:
            b = ctx.budget(x)
            rows.append([x.name, x.client or "", x.status, ", ".join(q["number"] for q in b["wonQuotes"]) or "—",
                         b["contract"], b["goods"], b["shipping"], b["clearing"], b["spent"], b["margin"],
                         f"{b['marginPct']}%" if b["marginPct"] is not None else "—", b["vendorOwed"]])
        n = lambda l: {"label": l, "align": "right", "num": True, "prefix": "₦ "}
        cols = [{"label": "Project"}, {"label": "Client"}, {"label": "Status"}, {"label": "Won quotes"}, n("Contract"), n("Goods"),
                n("Shipping"), n("Clearing"), n("Spent"), n("Margin"), {"label": "Margin %", "align": "right"}, n("Owed to vendors")]
        t = lambda i: round(sum(r[i] for r in rows), 2)
        contract, spent = t(4), t(8)
        secs = [{"columns": cols, "rows": rows, "empty": "No projects.",
                 "total": [f"{len(rows)} projects", "", "", "", contract, t(5), t(6), t(7), spent, t(9),
                           f"{round((contract - spent) / contract * 100, 1)}%" if contract else "—", t(11)]}]
        over = [r[0] for r in rows if r[4] and r[8] > r[4]]
        return {"title": "Budget vs actual", "subtitle": f"{len(rows)} projects · contract {_ngn(contract)} · spent {_ngn(spent)}",
                "landscape": True, "sections": secs,
                "summary": [{"label": "Contract value", "value": _ngn(contract)}, {"label": "Spent on imports", "value": _ngn(spent)},
                            {"label": "Margin so far", "value": _ngn(contract - spent), "color": "#047857" if contract >= spent else "#b91c1c"},
                            {"label": "Owed to vendors", "value": _ngn(t(11)), "color": "#b45309"}],
                "notes": ([f"Over budget: {', '.join(over)}"] if over else [])
                + ["Contract = won quotes excl. VAT at each quote's locked rate. Spent = goods + shipping + clearing of the project's shipments.", ctx.fx_note()]}
    elif rtype == "payables":
        rows = []
        for s in lst:
            if finance.vendor_balance(s) > 0.005 and s.value:
                rows.append([s.ref, "Vendor", ctx.vendor(s.vendor_id), STATUS_LABELS.get(s.status, s.status), s.payment_terms or "",
                             f"{s.currency} {finance.vendor_balance(s):,.2f}", ctx._money.usd(finance.vendor_balance(s), s.currency),
                             "Yes" if finance.payment_due(s) else ""])
            for label, c, who in (("Shipping", s.shipping_cost, ctx.shipper(s.shipper_id)),
                                  ("Clearing", s.clearing_cost, (ctx.agents.get(s.clearing_agent_id).name if ctx.agents.get(s.clearing_agent_id) else ""))):
                if c and c.get("total") and not c.get("paid"):
                    rows.append([s.ref, label, who, STATUS_LABELS.get(s.status, s.status), c.get("invoiceRef") or "",
                                 f"{c.get('currency')} {float(c.get('total')):,.2f}", ctx.cost_usd(c), "Yes"])
        rows.sort(key=lambda r: (r[7] != "Yes", -r[6]))
        cols = [{"label": "Shipment"}, {"label": "Owed for"}, {"label": "To"}, {"label": "Status"}, {"label": "Terms / ref"},
                {"label": "Amount"}, {**USD, "label": "USD"}, {"label": "Due now"}]
        total_usd = round(sum(r[6] for r in rows), 2)
        due_usd = round(sum(r[6] for r in rows if r[7] == "Yes"), 2)
        return {"title": "Payables", "subtitle": f"{len(rows)} unpaid items · {_money(total_usd)}", "landscape": True,
                "summary": [{"label": "Total owed", "value": _money(total_usd)}, {"label": "Due now", "value": _money(due_usd), "color": "#b91c1c"},
                            {"label": "Vendors", "value": _money(sum(r[6] for r in rows if r[1] == "Vendor"))},
                            {"label": "Shipping + clearing", "value": _money(sum(r[6] for r in rows if r[1] != "Vendor"))}],
                "sections": [{"columns": cols, "rows": rows, "total": [f"{len(rows)} items", "", "", "", "", "", total_usd, ""],
                              "empty": "Nothing owed. Everything is paid."}],
                "notes": ["Due now: vendor balances past their payment terms, and shipping/clearing invoices not marked paid.", ctx.fx_note()]}
    elif rtype == "costs":
        g = [s for s in lst if s.status in ("in_transit", "completed") or s.shipping_cost or s.clearing_cost]
        paid = lambda c: ("Paid" if c.get("paid") else "Unpaid") if c and c.get("total") else "—"
        rows = [[s.ref, s.description or "", STATUS_LABELS.get(s.status, s.status), ctx.shipper(s.shipper_id),
                 (ctx.agents.get(s.clearing_agent_id).name if ctx.agents.get(s.clearing_agent_id) else ""),
                 ctx.usd(s), ctx.cost_usd(s.shipping_cost), paid(s.shipping_cost), ctx.cost_usd(s.clearing_cost),
                 paid(s.clearing_cost), ctx.landed(s)] for s in g]
        num = lambda l: {**USD, "label": l}
        cols = [{"label": "Ref"}, {"label": "Description"}, {"label": "Status"}, {"label": "Shipper"}, {"label": "Clearing agent"},
                num("Goods (USD)"), num("Shipping (USD)"), {"label": "Paid"}, num("Clearing (USD)"), {"label": "Paid"}, num("Landed (USD)")]
        tot = lambda i: round(sum(r[i] for r in rows), 2)
        secs = [{"columns": cols, "rows": rows, "empty": "No shipped goods yet.",
                 "total": [f"{len(rows)} shipments", "", "", "", "", tot(5), tot(6), "", tot(8), "", tot(10)]}]
        missing = [s.ref for s in g if s.status == "in_transit" and (not (s.shipping_cost or {}).get("total") or not (s.clearing_cost or {}).get("total"))]
        unpaid = sum(1 for s in g for c in (s.shipping_cost, s.clearing_cost) if c and c.get("total") and not c.get("paid"))
        cards = [{"label": "Goods", "value": _money(tot(5))}, {"label": "Shipping", "value": _money(tot(6))},
                 {"label": "Clearing", "value": _money(tot(8))}, {"label": "Landed cost", "value": _money(tot(10)), "color": "#0f766e"}]
        note = []
        if missing:
            note.append(f"Costs still to record (in transit): {', '.join(missing)}")
        if unpaid:
            note.append(f"{unpaid} cost invoice(s) not marked paid")
        r = {"title": "Landed cost", "subtitle": f"{len(g)} shipped shipments · landed {_money(tot(10))}", "landscape": True,
             "summary": cards, "sections": secs, "notes": note + [ctx.fx_note()]}
        return r
    else:
        raise HTTPException(400, "Unknown report type")
    return {"title": title, "subtitle": f"{len(lst)} shipments · total {_money(ctx.total(lst))}", "landscape": True,
            "summary": cards, "sections": secs or [{"columns": SHIP_COLS, "rows": [], "empty": "No shipments yet."}],
            "notes": [ctx.fx_note()]}


def _doc_report(ctx, p):
    rtype = p.get("type") or "status"
    if rtype != "all":
        return _report(ctx, rtype)
    parts = [_report(ctx, t) for t in ("status", "project", "company", "vendor", "shipper", "costs", "budget", "payables")]
    secs = []
    for d in parts:
        secs.append({"heading": d["title"].upper(), "note": d["subtitle"]})
        secs += d["sections"]
    return {"title": "ImportFlow report", "subtitle": parts[0]["subtitle"], "landscape": True,
            "summary": parts[0]["summary"], "sections": secs, "notes": [ctx.fx_note()]}


BUILDERS = {
    "dashboard": _doc_dashboard, "shipments": _doc_shipments, "shipment": _doc_shipment,
    "projects": _doc_projects, "project": _doc_project, "report": _doc_report,
    "vendors": lambda c, p: _doc_partners(c, p, "vendors"), "shippers": lambda c, p: _doc_partners(c, p, "shippers"),
    "agents": lambda c, p: _doc_partners(c, p, "agents"),
}


def _build(db, kind, params):
    if kind not in BUILDERS:
        raise HTTPException(404, f"Unknown export. Valid: {sorted(BUILDERS)}")
    return BUILDERS[kind](_Ctx(db), params)


def _respond(doc, design, fmt, name, user, inline=False):
    stamp = datetime.now().strftime("%Y-%m-%d")
    base = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in name).strip("-") or "export"
    try:
        if fmt == "pdf":
            data = doc_export.render_pdf(doc, design, by=user.name)
            media, ext = "application/pdf", "pdf"
        else:
            data = doc_export.render_xlsx(doc, design, by=user.name)
            media, ext = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "xlsx"
    except PdfUnavailable as e:
        raise HTTPException(503, str(e))
    disp = content_disposition("inline" if inline else "attachment", f"{base}-{stamp}.{ext}")
    return StreamingResponse(io.BytesIO(data), media_type=media, headers={"Content-Disposition": disp})


@router.get("/export/{kind}")
def export(
    kind: str,
    format: str = "pdf",
    id: str | None = None,
    type: str | None = None,
    status: str | None = None,
    company: str | None = None,
    category: str | None = None,
    q: str | None = None,
    user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    if format not in ("pdf", "xlsx"):
        raise HTTPException(400, "format must be pdf or xlsx")
    params = {"id": id, "type": type, "status": status, "company": company, "category": category, "q": q}
    doc = _build(db, kind, params)
    name = {"shipment": doc["title"].replace("Shipment ", "shipment-"), "project": f"project-{doc['title']}",
            "report": f"report-{type or 'status'}"}.get(kind, kind)
    return _respond(doc, _design(db), format, name, user)

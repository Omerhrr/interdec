"""Excel (.xlsx) export for the native quotations module (openpyxl).

Mirrors the legacy facade app's deliverable so client documents stay consistent
after the migration: a "Work Breakdown" sheet (item cards + summary + totals +
payment terms + T&Cs) plus a "BOM Details" sheet (per-item cost build-up), and
a pipeline-wide summary workbook for the quotes list.

Note: the legacy export multiplied the qty-inclusive line price by qty again on
the item card ("Total Price"). We derive the per-unit selling price instead
(line / qty) so unit price x qty == line amount exactly.
"""
import io
from datetime import datetime

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.styles.colors import Color
from openpyxl.utils import get_column_letter

from . import pricing

NAVY = "1F3864"
HDR_BLUE = "2A4A6B"
TOTAL_BG = "E2EFDA"
GREY = "607080"
FONT = "Calibri"
NGN_FMT = '"\u20a6"#,##0'
NGN2_FMT = '"\u20a6"#,##0.00'


def _fmt_date(ms):
    try:
        return datetime.fromtimestamp(int(ms) / 1000).strftime("%d %b %Y")
    except (TypeError, ValueError, OSError):
        return ""


def _f(bold=False, sz=11, color=None):
    f = {"name": FONT, "sz": sz}
    if bold:
        f["bold"] = True
    if color:
        f["color"] = Color(rgb=color)
    return Font(**f)


def _fill(rgb):
    return PatternFill("solid", fgColor=rgb)


def _s(v, bold=False, sz=11, color=None, bg=None, halign=None, wrap=False, fmt=None):
    """String/label cell."""
    st = {"font": _f(bold, sz, color)}
    if bg:
        st["fill"] = _fill(bg)
    if halign or wrap:
        st["alignment"] = Alignment(horizontal=halign or "left", vertical="center", wrap_text=wrap)
    c = {"v": "" if v is None else str(v), "t": "s", "s": st}
    if fmt:
        c["z"] = fmt
    return c


def _n(v, bold=False, fmt=NGN_FMT, bg=None, halign="right"):
    """Numeric cell."""
    st = {"font": _f(bold)}
    if bg:
        st["fill"] = _fill(bg)
    if halign:
        st["alignment"] = Alignment(horizontal=halign, vertical="center")
    return {"v": round(v or 0, 2), "t": "n", "z": fmt, "s": st}


def _e():
    return {"v": "", "t": "s", "s": {"font": _f()}}


_THIN = Side(style="thin", color="000000")
_HAIR = Side(style="hair", color="000000")


def _b(cell, top=None, bottom=None, left=None, right=None):
    st = cell.setdefault("s", {})
    st.setdefault("font", _f())
    st["border"] = Border(
        top=_THIN if top else None, bottom=_THIN if bottom else None,
        left=_THIN if left else None, right=_THIN if right else None,
    )
    return cell


def _hb(cell, top=False, bottom=False, left=False, right=False):
    st = cell.setdefault("s", {})
    st.setdefault("font", _f())
    st["border"] = Border(
        top=_HAIR if top else None, bottom=_HAIR if bottom else None,
        left=_THIN if left else None, right=_THIN if right else None,
    )
    return cell


class _Sheet:
    """Row/col grid writer with merges, in the same spirit as the facade export."""

    def __init__(self):
        self.grid = {}
        self.merges = []
        self.max_r = 1
        self.max_c = 6

    def put(self, r, c, cell):
        self.grid[(r, c)] = cell
        self.max_r = max(self.max_r, r)
        return cell

    def merge(self, r1, c1, r2, c2):
        self.merges.append((r1, c1, r2, c2))
        self.max_r = max(self.max_r, r2)

    def to_ws(self, wb, title, cols, default_h=16):
        from openpyxl.worksheet.worksheet import Worksheet
        ws = wb.create_sheet(title)
        for (r, c), cell in self.grid.items():
            x = ws.cell(row=r, column=c)
            x.value = cell["v"]
            if cell.get("z"):
                x.number_format = cell["z"]
            st = cell.get("s") or {}
            if "font" in st:
                x.font = st["font"]
            if "fill" in st:
                x.fill = st["fill"]
            if "alignment" in st:
                x.alignment = st["alignment"]
            if "border" in st:
                x.border = st["border"]
        for r1, c1, r2, c2 in self.merges:
            ws.merge_cells(start_row=r1, start_column=c1, end_row=r2, end_column=c2)
        for i, wpx in enumerate(cols, start=1):
            ws.column_dimensions[get_column_letter(i)].width = max(6, wpx / 7.0)
        for r in range(1, self.max_r + 1):
            ws.row_dimensions[r].height = default_h
        return ws


def _item_cards(sh, items, markup):
    """Stacked item cards (rows of labelled fields), like the legacy layout."""
    CARD = 13
    LA, LF = 1, 6
    start = 4
    for i, it in enumerate(items):
        bom = it.get("bom") or {}
        qty = max(1, int(it.get("qty") or 1))
        line = bom.get("total") or 0
        selling = round(line * (1 + markup / 100.0))
        unit = round(selling / qty)
        base = start + i * CARD
        label = f"Item {i + 1}" + (f" \u2014 {it.get('position')}" if it.get("position") else "")
        sh.put(base, LA, _s(label, True, 11, "FFFFFF", NAVY))
        sh.merge(base, LA, base, LF)
        is_lm = it.get("product") == "balustrade"
        size = "Composite" if (it.get("elements") or []) else (
            f"{it.get('length')}m x {it.get('height')}mm" if is_lm else f"{it.get('width')} x {it.get('height')}mm")
        sub_ok = bool(it.get("hasSubframe"))
        mosq_ok = bool(it.get("hasMosq"))
        fields = [
            ("Position", it.get("position") or "\u2014", "s", False),
            ("Element Size", size, "s", False),
            ("Description", it.get("desc") or pricing.auto_desc(it), "s", True),
            ("System", (pricing._prod_by_id(it.get("product")) or {}).get("label") or "\u2014", "s", False),
            ("Profile Colour", "To be determined", "s", False),
            ("Sub-Frame", "Yes" if sub_ok else "\u2014", "s", False),
            ("Glazing", it.get("glassLabel") or "N/A", "s", True),
            ("Mosquito Net", "Yes" if mosq_ok else "\u2014", "s", False),
            ("Unit Price", unit, "n", False),
            ("Qty", qty, "q", False),
            ("Total Price", selling, "t", False),
        ]
        for fi, (lab, val, kind, wrap) in enumerate(fields):
            r = base + 1 + fi
            sh.put(r, LA, _s(lab, True, 11, None, None, "right"))
            sh.put(r, 2, _s(":", False, 11, None, None, "center"))
            if kind == "n":
                sh.put(r, 3, _n(val))
                sh.merge(r, 3, r, LF)
            elif kind == "q":
                cell = {"v": val, "t": "n", "z": '0" pcs"', "s": {"font": _f()}}
                sh.put(r, 3, cell)
                sh.merge(r, 3, r, LF)
            elif kind == "t":
                sh.put(r, 3, _n(val, True, NGN2_FMT))
                sh.merge(r, 3, r, LF)
            else:
                sh.put(r, 3, _s(val, False, 11, None, None, "left", wrap))
                sh.merge(r, 3, r, LF)
        for c in range(LA, LF + 1):
            sh.put(base + CARD - 1, c, _e())
    return start + len(items) * CARD


def _summary_block(sh, sum_start, items, markup, vat, rev):
    LA, LF = 1, 6
    sh.put(sum_start, LA, _s("SUMMARY", True, 12, "FFFFFF", NAVY))
    sh.merge(sum_start, LA, sum_start, LF)
    headers = [("DESCRIPTION", "left"), ("NO.", "center"), ("POSITION", "center"),
               ("QTY", "center"), ("RATE (\u20a6)", "right"), ("AMOUNT (\u20a6)", "right")]
    for ci, (h, ha) in enumerate(headers):
        sh.put(sum_start + 1, LA + ci, _b(_s(h, True, 11, "FFFFFF", HDR_BLUE, ha), "thin", "thin", "thin", "thin"))
    for i, it in enumerate(items):
        bom = it.get("bom") or {}
        qty = max(1, int(it.get("qty") or 1))
        selling = round((bom.get("total") or 0) * (1 + markup / 100.0))
        unit = round(selling / qty)
        r = sum_start + 2 + i
        sh.put(r, LA, _hb(_s(it.get("desc") or "", False, 11), "hair", "hair", "thin", "thin"))
        sh.put(r, 2, _hb(_s(str(i + 1), False, 11, None, None, "center"), "hair", "hair", "thin", "thin"))
        sh.put(r, 3, _hb(_s(it.get("position") or "", True, 11, NAVY, None, "center"), "hair", "hair", "thin", "thin"))
        qcell = {"v": qty, "t": "n", "z": '0" pcs"',
                 "s": {"font": _f(), "alignment": Alignment(horizontal="center"),
                       "border": Border(top=_HAIR, bottom=_HAIR, left=_THIN, right=_THIN)}}
        sh.put(r, 4, qcell)
        sh.put(r, 5, _hb(_n(unit), "hair", "hair", "thin", "thin"))
        sh.put(r, 6, _hb(_n(selling), "hair", "hair", "thin", "thin"))

    # Totals block (Sub-Total / VAT / optional logistics / GRAND TOTAL)
    t_start = sum_start + 2 + len(items) + 1
    logistics = float(rev.get("logisticsCost") or 0)
    rows = [("Sub-Total (excl. VAT)", rev.get("sub"), False),
            (f"VAT @ {rev.get('vatPct')}%", rev.get("vatAmt"), False)]
    if logistics:
        loc = f" to {rev['logisticsLocation']}" if rev.get("logisticsLocation") else ""
        rows.append((f"Transport & Logistics{loc}", logistics, False))
    rows.append(("GRAND TOTAL", rev.get("total"), True))
    for ri, (lab, val, gt) in enumerate(rows):
        r = t_start + ri
        bg = NAVY if gt else TOTAL_BG
        fg = "FFFFFF" if gt else None
        sh.put(r, LA, _b(_s(lab, gt, 11, fg, bg, "right"), None, None, "thin", None))
        sh.merge(r, LA, r, 5)
        sh.put(r, 6, _hb(_n(val, gt, NGN2_FMT if gt else "#,##0.00", bg), "hair", "hair", "thin", "thin"))
    return t_start + len(rows)


def _terms_block(sh, pt_start, rev, settings):
    LA, LF = 1, 6
    sh.put(pt_start, LA, _s("PAYMENT TERMS", True, 11, "FFFFFF", NAVY))
    sh.merge(pt_start, LA, pt_start, LF)
    sh.put(pt_start + 1, LA, _s(rev.get("paymentTerms") or settings.get("paymentTerms") or "", False, 10, None, None, "left", True))
    sh.merge(pt_start + 1, LA, pt_start + 2, LF)
    tcs = settings.get("tcs") or ""
    if tcs:
        tc = pt_start + 4
        sh.put(tc - 1, LA, _s("TERMS & CONDITIONS", True, 11, "FFFFFF", NAVY))
        sh.merge(tc - 1, LA, tc - 1, LF)
        lines = [l for l in tcs.split("\n") if l.strip()]
        for li, line in enumerate(lines):
            sh.put(tc + li, LA, _s(line, False, 10, None, None, "left", True))
            sh.merge(tc + li, LA, tc + li, LF)


def build_quote_workbook(quote: dict, rev: dict, catalog: dict) -> bytes:
    """Single-revision workbook: Work Breakdown + BOM Details (legacy layout)."""
    settings = catalog.get("settings") or pricing.SETTINGS_DEF
    markup = float(rev.get("markupPct") or 0)
    vat = float(rev.get("vatPct") or 0)
    items = rev.get("items") or []

    wb = Workbook()
    wb.remove(wb.active)

    sh = _Sheet()
    title = quote.get("projectName") or quote.get("clientName") or "Quotation"
    if quote.get("clientName") and quote.get("projectName"):
        title = f"{quote['projectName']} \u2014 {quote['clientName']}"
    subtitle = f"{quote.get('number', '')} Rev.{rev.get('rev', 0)}"
    if quote.get("salesPerson"):
        subtitle += f" | {quote['salesPerson']}"
    subtitle += f"   Date: {_fmt_date(rev.get('created'))}   Valid: {rev.get('validityDays', 14)} days"
    sh.put(1, 1, _s(title, True, 13))
    sh.merge(1, 1, 1, 6)
    sh.put(2, 1, _s(subtitle, False, 10, GREY))
    sh.merge(2, 1, 2, 6)

    sum_start = _item_cards(sh, items, markup)
    after_totals = _summary_block(sh, sum_start, items, markup, vat, rev)
    _terms_block(sh, after_totals + 1, rev, settings)

    ws = sh.to_ws(wb, "Work Breakdown", [280, 35, 120, 65, 100, 110])
    for r in range(1, sh.max_r + 1):
        pos = (r - 4) % 13
        if r >= 4:
            ws.row_dimensions[r].height = 18 if pos == 0 else (6 if pos == 12 else 16)
        elif r == 1:
            ws.row_dimensions[r].height = 22

    # ---- BOM Details sheet ----
    b = _Sheet()
    b.max_c = 17
    hdrs = ["#", "Pos.", "Description", "W (mm)", "H (mm)", "Area m\u00b2", "Profiles", "Glass/Panel",
            "Gasket", "Sealant", "Hardware", "Sub-Frame", "Mosq. Net", "Fabrication", "Installation",
            "Total Cost", "Selling"]
    for ci, h in enumerate(hdrs, start=1):
        b.put(1, ci, _s(h, True, 11, "FFFFFF", NAVY, "center"))
    for i, it in enumerate(items):
        bom = it.get("bom") or {}
        is_lm = it.get("product") == "balustrade"
        w = it.get("length") * 1000 if is_lm else it.get("width")
        selling = round((bom.get("total") or 0) * (1 + markup / 100.0))
        r = 2 + i
        vals = [
            _n(i + 1, False, "#,##0", None, "right"),
            _s(it.get("position") or "", True),
            _s(it.get("desc") or ""),
            _n(w, False, "#,##0"), _n(it.get("height"), False, "#,##0"),
            _n(bom.get("area"), False, "#,##0.00"),
            _n(bom.get("profileCost")), _n(bom.get("glassCost")), _n(bom.get("gasketCost")),
            _n(bom.get("sealantCost")), _n(bom.get("hwCost")), _n(bom.get("subframeCost")),
            _n(bom.get("mosqCost")), _n(bom.get("fabCost")), _n(bom.get("instCost")),
            _n(bom.get("total"), True), _n(selling, True),
        ]
        for ci, cell in enumerate(vals, start=1):
            b.put(r, ci, cell)
    n = len(items)
    tr = 2 + n + 1
    sums = {}
    for key in ("area", "profileCost", "glassCost", "gasketCost", "sealantCost", "hwCost",
                "subframeCost", "mosqCost", "fabCost", "instCost"):
        sums[key] = sum(round((it.get("bom") or {}).get(key) or 0) for it in items)
    blank = [_e() for _ in range(17)]
    for ci, cell in enumerate(blank, start=1):
        b.put(tr, ci, cell)
    b.put(tr, 3, _s("TOTALS", True, 11, None, TOTAL_BG))
    for ci, key in [(6, "area"), (7, "profileCost"), (8, "glassCost"), (9, "gasketCost"),
                    (10, "sealantCost"), (11, "hwCost"), (12, "subframeCost"), (13, "mosqCost"),
                    (14, "fabCost"), (15, "instCost")]:
        b.put(tr, ci, _n(sums[key], True, "#,##0.00" if key == "area" else "#,##0", TOTAL_BG))
    b.put(tr, 16, _n(rev.get("cost"), True, "#,##0", TOTAL_BG))
    b.put(tr, 17, _n(rev.get("sub"), True, "#,##0", TOTAL_BG))
    money_rows = [("Total Cost", rev.get("cost")), (f"Markup {markup:g}%", rev.get("mkAmt")),
                  ("Sub-Total", rev.get("sub")), (f"VAT {vat:g}%", rev.get("vatAmt"))]
    logistics = float(rev.get("logisticsCost") or 0)
    if logistics:
        loc = f" to {rev['logisticsLocation']}" if rev.get("logisticsLocation") else ""
        money_rows.insert(3, (f"Transport & Logistics{loc}", logistics))
    for ri, (lab, val) in enumerate(money_rows):
        r = tr + 1 + ri
        for ci in range(1, 18):
            b.put(r, ci, _e())
        b.put(r, 15, _s(lab, True, 11, None, TOTAL_BG, "right"))
        b.put(r, 16, _n(val, True, NGN2_FMT, TOTAL_BG))
    gr = tr + 1 + len(money_rows)
    for ci in range(1, 18):
        b.put(gr, ci, _e())
    b.put(gr, 15, _s("GRAND TOTAL", True, 12, "FFFFFF", NAVY, "right"))
    b.put(gr, 16, {"v": round(rev.get("total") or 0, 2), "t": "n", "z": NGN2_FMT,
                   "s": {"font": _f(True, 12, "FFD700"), "fill": _fill(NAVY)}})
    b.to_ws(wb, "BOM Details",
            [28, 49, 238, 63, 63, 70, 98, 98, 84, 84, 84, 84, 77, 98, 98, 112, 112])

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def build_quotes_list_workbook(quotes: list) -> bytes:
    """Pipeline-wide summary: one row per quote (latest revision) + revision sheet."""
    wb = Workbook()
    wb.remove(wb.active)
    sh = _Sheet()
    sh.max_c = 12
    sh.put(1, 1, _s("Interdec Platform \u2014 Quotations Summary", True, 13))
    sh.merge(1, 1, 1, 12)
    sh.put(2, 1, _s(f"Generated {_fmt_date(int(datetime.now().timestamp() * 1000))} \u00b7 {len(quotes)} quote(s)", False, 10, GREY))
    sh.merge(2, 1, 2, 12)
    hdrs = ["#", "Number", "Client", "Project", "Sales", "Status", "Rev", "Markup %", "VAT %",
            "Logistics", "Total (\u20a6)", "Updated"]
    for ci, h in enumerate(hdrs, start=1):
        sh.put(4, ci, _b(_s(h, True, 10, "FFFFFF", HDR_BLUE, "center"), "thin", "thin", "thin", "thin"))
    r = 5
    total_sum = 0
    for i, q in enumerate(quotes):
        latest = q.get("latest") or {}
        total_sum += float(q.get("total") or 0)
        vals = [
            _n(i + 1, False, "#,##0", None, "center"),
            _s(q.get("number") or "", True),
            _s(q.get("clientName") or "N/A"),
            _s(q.get("projectName") or "N/A"),
            _s(q.get("salesPerson") or "N/A"),
            _s((q.get("status") or "draft").capitalize()),
            _n(latest.get("rev") if latest else 0, False, "0", None, "center"),
            _n(latest.get("markupPct") if latest else 0, False, "0.0\"%\"", None, "center"),
            _n(latest.get("vatPct") if latest else 0, False, "0.0\"%\"", None, "center"),
            _n(latest.get("logisticsCost") if latest else 0),
            _n(q.get("total"), True),
            _s(_fmt_date(q.get("updated"))),
        ]
        for ci, cell in enumerate(vals, start=1):
            sh.put(r, ci, cell)
        r += 1
    sh.put(r, 1, _b(_s("TOTAL", True, 11, "FFFFFF", NAVY, "right"), "thin", None, "thin", "thin"))
    sh.merge(r, 1, r, 11)
    sh.put(r, 12, _hb(_n(total_sum, True), "hair", "hair", "thin", "thin"))
    sh.to_ws(wb, "Quotes", [28, 110, 170, 170, 140, 80, 42, 70, 60, 100, 130, 90])

    # Revisions detail sheet
    b = _Sheet()
    b.max_c = 10
    rh = ["Number", "Rev", "Status", "Items", "Cost", "Markup", "Sub-Total", "VAT", "Logistics", "Total"]
    for ci, h in enumerate(rh, start=1):
        b.put(1, ci, _s(h, True, 10, "FFFFFF", HDR_BLUE, "center"))
    r = 2
    for q in quotes:
        for rev in q.get("revisions") or []:
            cells = [
                _s(q.get("number") or "", True), _n(rev.get("rev"), False, "0", None, "center"),
                _s((rev.get("status") or "").capitalize()),
                _n(len(rev.get("items") or []), False, "0", None, "center"),
                _n(rev.get("cost")), _n(rev.get("mkAmt")), _n(rev.get("sub")),
                _n(rev.get("vatAmt")), _n(rev.get("logisticsCost")), _n(rev.get("total"), True),
            ]
            for ci, cell in enumerate(cells, start=1):
                b.put(r, ci, cell)
            r += 1
    b.to_ws(wb, "Revisions", [110, 42, 80, 50, 110, 110, 110, 100, 100, 120])

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()

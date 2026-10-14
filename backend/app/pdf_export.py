"""Client quotation PDF (WeasyPrint).

The look is driven by the admin's PDF Design settings (catalogue key
"pdfDesign"): company details and logo, colours, font, header layout and which
sections appear. Only selling prices are ever rendered — costs and markup never
reach the client document.

WeasyPrint needs Pango at the OS level. It is imported lazily so the rest of
the API keeps working on a machine without it; the endpoint then explains what
to install instead of crashing the server.
"""
import base64
import re
from datetime import datetime, timedelta

from jinja2 import Environment, BaseLoader, select_autoescape

from . import pricing

SYMBOLS = {"NGN": "₦", "USD": "$", "EUR": "€", "GBP": "£", "JPY": "¥", "CNY": "¥",
           "ILS": "₪", "AED": "AED ", "GHS": "GH₵", "ZAR": "R", "KES": "KSh "}

FONTS = {
    "sans": "'DejaVu Sans', 'Liberation Sans', Arial, sans-serif",
    "arial": "'Liberation Sans', Arial, Helvetica, sans-serif",
    "serif": "'DejaVu Serif', 'Liberation Serif', Georgia, serif",
    "times": "'Liberation Serif', 'Times New Roman', serif",
}
LAYOUTS = ("classic", "banner", "minimal")
PAPERS = ("A4", "Letter")

DEFAULT_DESIGN = {
    "companyName": "Interdec Facade",
    "tagline": "Aluminium & Glass Systems",
    "address": "",
    "phone": "",
    "email": "",
    "website": "",
    "taxId": "",
    "logo": "",                  # data: URL (png / jpeg / svg / webp)
    "logoHeight": 44,            # px
    "brandColor": "#1F3864",
    "accentColor": "#E8A33D",
    "font": "sans",
    "layout": "classic",
    "paper": "A4",
    "title": "QUOTATION",
    "intro": "Thank you for your enquiry. We are pleased to submit our quotation as follows:",
    "footerText": "Thank you for the opportunity to quote.",
    "bankDetails": "",
    "signatureName": "",
    "signatureTitle": "",
    "show": {
        "specs": True,           # glass / finish line under each item
        "size": True,
        "position": True,
        "sketch": False,         # small dimension drawing per item
        "unitPrice": True,
        "paymentTerms": True,
        "terms": True,
        "bank": True,
        "signature": True,
        "pageNumbers": True,
        "salesPerson": True,
    },
}

HEX = re.compile(r"^#[0-9a-fA-F]{6}$")
LOGO_TYPES = ("image/png", "image/jpeg", "image/svg+xml", "image/webp", "image/gif")
MAX_LOGO_BYTES = 600 * 1024


class PdfUnavailable(RuntimeError):
    pass


def merged_design(saved):
    d = {**DEFAULT_DESIGN, **{k: v for k, v in (saved or {}).items() if k != "show"}}
    d["show"] = {**DEFAULT_DESIGN["show"], **((saved or {}).get("show") or {})}
    return d


def validate_design(value: dict) -> str | None:
    """Return an error message, or None if the design is acceptable."""
    if not isinstance(value, dict):
        return "Design must be an object"
    for k in ("brandColor", "accentColor"):
        if value.get(k) and not HEX.match(str(value[k])):
            return f"{k} must be a colour like #1F3864"
    if value.get("font") and value["font"] not in FONTS:
        return f"font must be one of {sorted(FONTS)}"
    if value.get("layout") and value["layout"] not in LAYOUTS:
        return f"layout must be one of {list(LAYOUTS)}"
    if value.get("paper") and value["paper"] not in PAPERS:
        return f"paper must be one of {list(PAPERS)}"
    logo = value.get("logo") or ""
    if logo:
        m = re.match(r"^data:([\w/+.-]+);base64,(.*)$", logo, re.S)
        if not m or m.group(1) not in LOGO_TYPES:
            return "Logo must be a PNG, JPG, SVG, WebP or GIF image"
        try:
            raw = base64.b64decode(m.group(2), validate=True)
        except Exception:
            return "Logo file is not valid"
        if len(raw) > MAX_LOGO_BYTES:
            return "Logo must be smaller than 600 KB"
    try:
        h = float(value.get("logoHeight", 44))
        if not 16 <= h <= 140:
            return "Logo height must be between 16 and 140"
    except (TypeError, ValueError):
        return "Logo height must be a number"
    for k, v in value.items():
        if isinstance(v, str) and len(v) > 4000 and k != "logo":
            return f"{k} is too long"
    return None


# ---------------------------------------------------------------------------
# helpers used by the template
# ---------------------------------------------------------------------------

def _money(v, code):
    v = float(v or 0)
    sym = SYMBOLS.get((code or "NGN").upper(), (code or "") + " ")
    whole = (code or "NGN").upper() in ("NGN", "JPY")
    return sym + (f"{v:,.0f}" if whole else f"{v:,.2f}")


def _date(ms):
    try:
        return datetime.fromtimestamp(int(ms) / 1000)
    except (TypeError, ValueError, OSError):
        return datetime.now()


def _size(it):
    if it.get("product") == "balustrade":
        return f"{pricing._f(it.get('length')):g} m × {pricing._f(it.get('height')):g} mm"
    return f"{pricing._f(it.get('width')):g} × {pricing._f(it.get('height')):g} mm"


def _sketch(it, color):
    """Tiny proportional elevation drawing with panel splits, as inline SVG."""
    if it.get("product") in ("balustrade", "acp"):
        return ""
    w, h = pricing._f(it.get("width")), pricing._f(it.get("height"))
    if w <= 0 or h <= 0:
        return ""
    box = 54.0
    s = box / max(w, h)
    rw, rh = max(w * s, 6), max(h * s, 6)
    x0, y0 = (box - rw) / 2 + 2, (box - rh) / 2 + 2
    sub = it.get("subTypeId") or ""
    panels = 4 if sub.endswith("s4") else 3 if sub.endswith("s3") else 2 if (sub.endswith("s2") or sub.endswith("double")) else 1
    lines = "".join(
        f'<line x1="{x0 + rw * i / panels:.1f}" y1="{y0:.1f}" x2="{x0 + rw * i / panels:.1f}" y2="{y0 + rh:.1f}" stroke="{color}" stroke-width="0.8"/>'
        for i in range(1, panels)
    )
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="58" height="58" viewBox="0 0 58 58">'
            f'<rect x="{x0:.1f}" y="{y0:.1f}" width="{rw:.1f}" height="{rh:.1f}" fill="#eef4fb" stroke="{color}" stroke-width="1.2"/>'
            f'{lines}</svg>')


def _tags(it):
    t = []
    if it.get("hasSubframe"):
        t.append("Sub-frame")
    if it.get("hasMosq"):
        t.append("Mosquito net")
    for x in (it.get("bom") or {}).get("extras") or []:
        t.append(x.get("name"))
    return ", ".join(x for x in t if x)


TEMPLATE = r"""<!doctype html>
<html><head><meta charset="utf-8"><title>{{ quote.number }}</title>
<style>
@page {
  size: {{ d.paper }}; margin: 16mm 14mm 20mm;
  {% if d.show.pageNumbers or d.footerText %}
  @bottom-left { content: "{{ footer_css|safe }}"; font-family: {{ font|safe }}; font-size: 7.5pt; color: #7a8594; }
  {% endif %}
  {% if d.show.pageNumbers %}
  @bottom-right { content: "Page " counter(page) " of " counter(pages); font-family: {{ font|safe }}; font-size: 7.5pt; color: #7a8594; }
  {% endif %}
}
* { box-sizing: border-box; }
body { font-family: {{ font|safe }}; font-size: 9pt; color: #1f2937; margin: 0; line-height: 1.4; }
.brand { color: {{ d.brandColor }}; }
.head { display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; padding-bottom: 12px; }
.head > div:first-child { flex: 1; min-width: 0; }
.doc { flex: 0 0 auto; }
.classic .head { border-bottom: 2.5pt solid {{ d.brandColor }}; }
.banner .head { background: {{ d.brandColor }}; color: #fff; margin: -16mm -14mm 0; padding: 14mm 14mm 9mm; }
.banner .head .co-name, .banner .head .doc-title { color: #fff; }
.banner .head .muted { color: rgba(255,255,255,.8); }
.minimal .head { border-bottom: 0.6pt solid #d6dce4; }
.logo { height: {{ d.logoHeight }}px; max-width: 220px; object-fit: contain; display: block; margin-bottom: 6px; }
.co-name { font-size: 15pt; font-weight: 700; color: {{ d.brandColor }}; letter-spacing: -.2px; }
.tagline { font-size: 8.5pt; color: #64748b; }
.co-lines { font-size: 7.8pt; color: #64748b; margin-top: 4px; }
.doc { text-align: right; }
.doc-title { font-size: 20pt; font-weight: 800; letter-spacing: 1.5px; color: {{ d.brandColor }}; }
.minimal .doc-title { font-weight: 400; letter-spacing: 4px; font-size: 17pt; }
.doc-meta { font-size: 8.5pt; margin-top: 3px; }
.muted { color: #64748b; }
.bar { height: 3pt; background: {{ d.accentColor }}; margin: 0 0 14px; }
.classic .bar, .minimal .bar { display: none; }
.meta { display: flex; gap: 24px; margin: 14px 0 10px; }
.meta > div { flex: 1; }
.lbl { font-size: 7pt; font-weight: 700; letter-spacing: .9px; text-transform: uppercase; color: {{ d.accentColor }}; margin-bottom: 2px; }
.minimal .lbl { color: #64748b; }
.v-strong { font-weight: 700; font-size: 10pt; }
.intro { margin: 4px 0 12px; }
table { width: 100%; border-collapse: collapse; }
thead { display: table-header-group; }
th { background: {{ d.brandColor }}; color: #fff; font-size: 7.5pt; font-weight: 700; text-transform: uppercase; letter-spacing: .5px; padding: 6px 7px; text-align: left; }
.minimal th { background: none; color: #475569; border-bottom: 1.2pt solid {{ d.brandColor }}; }
td { padding: 7px; border-bottom: 0.5pt solid #e2e8f0; vertical-align: top; }
tr { page-break-inside: avoid; }
tbody tr:nth-child(even) td { background: #f8fafc; }
.minimal tbody tr:nth-child(even) td { background: none; }
.r { text-align: right; white-space: nowrap; }
.c { text-align: center; }
.desc { font-weight: 700; }
.spec { font-size: 8pt; color: #475569; margin-top: 1px; }
.pos { color: {{ d.brandColor }}; font-weight: 700; }
.sk { width: 62px; }
.totals { margin-left: auto; width: 46%; margin-top: 10px; page-break-inside: avoid; }
.totals div { display: flex; justify-content: space-between; padding: 4px 8px; }
.totals .grand { background: {{ d.brandColor }}; color: #fff; font-weight: 800; font-size: 11pt; padding: 8px; margin-top: 4px; }
.minimal .totals .grand { background: none; color: {{ d.brandColor }}; border-top: 1.5pt solid {{ d.brandColor }}; }
.blocks { margin-top: 18px; }
.block { margin-bottom: 12px; page-break-inside: avoid; }
.block .txt { white-space: pre-line; font-size: 8.5pt; }
.two { display: flex; gap: 24px; }
.two > div { flex: 1; }
.sign { margin-top: 26px; display: flex; gap: 40px; page-break-inside: avoid; }
.sign > div { flex: 1; }
.sign .line { border-top: 0.7pt solid #94a3b8; margin-top: 34px; padding-top: 4px; font-size: 8pt; }
.fx { font-size: 7.5pt; color: #64748b; text-align: right; margin-top: 4px; }
</style></head>
<body class="{{ d.layout }}">
<div class="head">
  <div>
    {% if d.logo %}<img class="logo" src="{{ d.logo }}" alt="">{% endif %}
    {% if not d.logo or d.layout != 'minimal' %}<div class="co-name">{{ d.companyName }}</div>{% endif %}
    {% if d.tagline %}<div class="tagline muted">{{ d.tagline }}</div>{% endif %}
    <div class="co-lines muted">
      {% if d.address %}{{ d.address }}<br>{% endif %}
      {{ [d.phone, d.email, d.website]|select|join("  ·  ") }}
      {% if d.taxId %}<br>{{ d.taxId }}{% endif %}
    </div>
  </div>
  <div class="doc">
    <div class="doc-title">{{ d.title }}</div>
    <div class="doc-meta"><b>{{ quote.number }}</b>{% if rev.rev %} · Rev.{{ rev.rev }}{% endif %}</div>
    <div class="doc-meta muted">Date: {{ issued.strftime("%d %b %Y") }}</div>
    <div class="doc-meta muted">Valid until: {{ valid_to.strftime("%d %b %Y") }}</div>
  </div>
</div>
<div class="bar"></div>

<div class="meta">
  <div>
    <div class="lbl">Prepared for</div>
    <div class="v-strong">{{ quote.clientName or "—" }}</div>
    {% if quote.clientPhone %}<div>{{ quote.clientPhone }}</div>{% endif %}
    {% if quote.clientEmail %}<div>{{ quote.clientEmail }}</div>{% endif %}
  </div>
  <div>
    {% if quote.projectName %}<div class="lbl">Project</div><div class="v-strong">{{ quote.projectName }}</div>{% endif %}
    {% if d.show.salesPerson and quote.salesPerson %}<div class="lbl"{% if quote.projectName %} style="margin-top:6px"{% endif %}>Contact person</div><div>{{ quote.salesPerson }}</div>{% endif %}
  </div>
  <div>
    <div class="lbl">Currency</div><div>{{ code }}</div>
  </div>
</div>

{% if d.intro %}<div class="intro">{{ d.intro }}</div>{% endif %}

<table>
  <thead><tr>
    <th style="width:22px">#</th>
    {% if d.show.sketch %}<th class="sk"></th>{% endif %}
    <th>Description</th>
    {% if d.show.size %}<th>Size</th>{% endif %}
    <th class="c">Qty</th>
    {% if d.show.unitPrice %}<th class="r">Unit price</th>{% endif %}
    <th class="r">Amount</th>
  </tr></thead>
  <tbody>
  {% for it in items %}
    <tr>
      <td>{{ loop.index }}</td>
      {% if d.show.sketch %}<td class="sk">{{ it.sketch|safe }}</td>{% endif %}
      <td>
        <div class="desc">{{ it.desc }}{% if d.show.position and it.position %} <span class="pos">· {{ it.position }}</span>{% endif %}</div>
        {% if d.show.specs and it.glassLabel and it.glassLabel != "N/A" %}<div class="spec">{{ it.glassLabel }}</div>{% endif %}
        {% if d.show.specs and it.tags %}<div class="spec">{{ it.tags }}</div>{% endif %}
        {% if it.note %}<div class="spec">{{ it.note }}</div>{% endif %}
      </td>
      {% if d.show.size %}<td style="white-space:nowrap">{{ it.size }}</td>{% endif %}
      <td class="c">{{ it.qty }}</td>
      {% if d.show.unitPrice %}<td class="r">{{ it.unit }}</td>{% endif %}
      <td class="r"><b>{{ it.amount }}</b></td>
    </tr>
  {% endfor %}
  </tbody>
</table>

<div class="totals">
  <div><span>Sub-total (excl. VAT)</span><span>{{ m(rev.sub) }}</span></div>
  <div><span>VAT ({{ "%g"|format(rev.vatPct or 0) }}%)</span><span>{{ m(rev.vatAmt) }}</span></div>
  {% if (rev.logisticsCost or 0) > 0 %}<div><span>Transport &amp; logistics{% if rev.logisticsLocation %} to {{ rev.logisticsLocation }}{% endif %}</span><span>{{ m(rev.logisticsCost) }}</span></div>{% endif %}
  <div class="grand"><span>TOTAL ({{ code }})</span><span>{{ m(rev.total) }}</span></div>
</div>

<div class="blocks">
  <div class="two">
    {% if d.show.paymentTerms and payment_terms %}<div class="block"><div class="lbl">Payment terms</div><div class="txt">{{ payment_terms }}</div></div>{% endif %}
    {% if d.show.bank and d.bankDetails %}<div class="block"><div class="lbl">Bank details</div><div class="txt">{{ d.bankDetails }}</div></div>{% endif %}
  </div>
  {% if d.show.terms and tcs %}<div class="block"><div class="lbl">Terms &amp; conditions</div><div class="txt">{{ tcs }}</div></div>{% endif %}
</div>

{% if d.show.signature %}
<div class="sign">
  <div><div class="line">For {{ d.companyName }}{% if d.signatureName %}<br><b>{{ d.signatureName }}</b>{% endif %}{% if d.signatureTitle %}<br><span class="muted">{{ d.signatureTitle }}</span>{% endif %}</div></div>
  <div><div class="line">Accepted by client (name, signature &amp; date)</div></div>
</div>
{% endif %}
</body></html>
"""

_env = Environment(loader=BaseLoader(), autoescape=select_autoescape(default=True, default_for_string=True))
_tpl = _env.from_string(TEMPLATE)


def render_html(quote: dict, rev: dict, settings: dict, design: dict) -> str:
    d = merged_design(design)
    code = (rev.get("currency") or "NGN").upper()
    markup = pricing._f(rev.get("markupPct"))
    issued = _date(rev.get("created"))
    items = []
    for it in rev.get("items") or []:
        bom = it.get("bom") or {}
        qty = max(1, int(pricing._f(it.get("qty"), 1) or 1))
        selling = pricing._f(bom.get("total")) * (1 + markup / 100.0)
        # same rounding as the app: whole naira, cents for other currencies
        selling = round(selling) if code in ("NGN", "JPY") else round(selling, 2)
        items.append({
            "desc": it.get("desc") or "Item", "position": it.get("position") or "", "note": it.get("note") or "",
            "glassLabel": it.get("glassLabel") or "", "tags": _tags(it), "qty": qty, "size": _size(it),
            "unit": _money(selling / qty, code), "amount": _money(selling, code),
            "sketch": _sketch(it, d["brandColor"]) if d["show"]["sketch"] else "",
        })
    # goes into a CSS string: strip anything that could end it
    footer = re.sub(r'[\\"<>\n\r]', " ", d.get("footerText") or "")[:200]
    return _tpl.render(
        d=d, quote=quote, rev=rev, code=code, items=items, issued=issued,
        valid_to=issued + timedelta(days=int(pricing._f(rev.get("validityDays"), 14) or 14)),
        payment_terms=rev.get("paymentTerms") or settings.get("paymentTerms") or "",
        tcs=settings.get("tcs") or "",
        font=FONTS.get(d["font"], FONTS["sans"]),
        footer_css=footer,
        m=lambda v: _money(v, code),
    )


def _data_only_fetcher():
    """Only inline data: URLs may be loaded (logos); never the network or disk."""
    try:  # WeasyPrint 66+
        from weasyprint.urls import URLFetcher
        return URLFetcher(allowed_protocols=["data"])
    except ImportError:  # older WeasyPrint: function-style fetcher
        from weasyprint.urls import default_url_fetcher

        def fetch(url, *a, **kw):
            if not url.startswith("data:"):
                raise ValueError("External resources are not allowed in quotation PDFs")
            return default_url_fetcher(url, *a, **kw)
        return fetch


def render_pdf(quote: dict, rev: dict, settings: dict, design: dict) -> bytes:
    try:
        from weasyprint import HTML
    except Exception as e:  # pragma: no cover - depends on the OS
        raise PdfUnavailable(
            "PDF export needs WeasyPrint. Install it with `pip install weasyprint` "
            "(and on Linux/WSL: `sudo apt install libpango-1.0-0 libpangoft2-1.0-0`)."
        ) from e
    html = render_html(quote, rev, settings, design)
    return HTML(string=html, url_fetcher=_data_only_fetcher()).write_pdf()

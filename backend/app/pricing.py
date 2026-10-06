"""Facade pricing engine — server-side port of the original calcBOMSingle.

Faithful transcription of the calculation logic audited in the company build
(facade.html lines 46-221). All rates are in Nigerian Naira. The port keeps
two intentional quirks of the source engine, flagged in the audit as
"confirm with the business" items:

  QUIRK 1 (sealant without subframe): sealant is charged for every subtype in
  SUBFRAME_ELIGIBLE regardless of the hasSubframe flag, while the subframe
  itself is only charged when hasSubframe is true.

  QUIRK 2 (composite subframe rule): on composite items the subframe is
  measured as 1.5 x (W + H) per element x qty (shared edges), replacing the
  normal 2W + 2H per-item perimeter.
"""
import math
from copy import deepcopy

# ---------------------------------------------------------------------------
# Catalogue defaults (mirrors facade.html PRODS/SUBS/HW/GC/RATES/SETTINGS)
# ---------------------------------------------------------------------------

PRODS = [
    {"id": "et_window", "label": "EUROTEC Aluminium Window", "icon": "window", "unit": "m2", "isLm": False, "brand": "EUROTEC"},
    {"id": "ct_window", "label": "CORTIZO Aluminium Window", "icon": "window", "unit": "m2", "isLm": False, "brand": "CORTIZO"},
    {"id": "et_door", "label": "EUROTEC Aluminium Door", "icon": "door", "unit": "m2", "isLm": False, "brand": "EUROTEC"},
    {"id": "ct_door", "label": "CORTIZO Aluminium Door", "icon": "door", "unit": "m2", "isLm": False, "brand": "CORTIZO"},
    {"id": "et_cw", "label": "EUROTEC Curtain Wall", "icon": "building", "unit": "m2", "isLm": False, "brand": "EUROTEC"},
    {"id": "ct_cw", "label": "CORTIZO Curtain Wall", "icon": "building", "unit": "m2", "isLm": False, "brand": "CORTIZO"},
    {"id": "ct_minimal", "label": "CORTIZO Minimal Sliding Door", "icon": "door", "unit": "m2", "isLm": False, "brand": "CORTIZO"},
    {"id": "structural", "label": "Frameless Spider Glass Wall", "icon": "bolt", "unit": "m2", "isLm": False},
    {"id": "acp", "label": "ACP Cladding", "icon": "cladding", "unit": "m2", "isLm": False},
    {"id": "balustrade", "label": "Glass Balustrade", "icon": "shield", "unit": "lm", "isLm": True},
    {"id": "shower", "label": "Frameless Shower", "icon": "shower", "unit": "m2", "isLm": False},
]

SUBS = {
    "et_window": [
        {"id": "etw_fixed", "label": "Fixed Light", "kg": 7},
        {"id": "etw_single", "label": "Single Casement", "kg": 11},
        {"id": "etw_double", "label": "Double Casement", "kg": 12},
        {"id": "etw_s2", "label": "2-Panel Sliding", "kg": 7},
        {"id": "etw_s3", "label": "3-Panel Sliding", "kg": 10},
        {"id": "etw_s4", "label": "4-Panel Sliding", "kg": 13},
    ],
    "ct_window": [
        {"id": "ctw_fixed", "label": "Fixed Light", "kg": 7},
        {"id": "ctw_single", "label": "Single Casement", "kg": 11},
        {"id": "ctw_double", "label": "Double Casement", "kg": 12},
        {"id": "ctw_s2", "label": "2-Panel Sliding", "kg": 7},
        {"id": "ctw_s3", "label": "3-Panel Sliding", "kg": 10},
        {"id": "ctw_s4", "label": "4-Panel Sliding", "kg": 13},
    ],
    "et_door": [
        {"id": "etd_single", "label": "Single Leaf Hinged", "kg": 9},
        {"id": "etd_double", "label": "Double Leaf Hinged", "kg": 10},
        {"id": "etd_s2", "label": "2-Panel Sliding", "kg": 8},
        {"id": "etd_s3", "label": "3-Panel Sliding", "kg": 11},
        {"id": "etd_s4", "label": "4-Panel Sliding", "kg": 14},
    ],
    "ct_door": [
        {"id": "ctd_single", "label": "Single Leaf Hinged", "kg": 9},
        {"id": "ctd_double", "label": "Double Leaf Hinged", "kg": 10},
        {"id": "ctd_s2", "label": "2-Panel Sliding", "kg": 8},
        {"id": "ctd_s3", "label": "3-Panel Sliding", "kg": 11},
        {"id": "ctd_s4", "label": "4-Panel Sliding", "kg": 14},
    ],
    "et_cw": [{"id": "etcw_g", "label": "Curtain Wall", "kg": 14}],
    "ct_cw": [{"id": "ctcw_g", "label": "Curtain Wall", "kg": 14}],
    "ct_minimal": [
        {"id": "ctm_s2", "label": "2-Panel Sliding", "kg": 10},
        {"id": "ctm_s3", "label": "3-Panel Sliding", "kg": 13},
        {"id": "ctm_s4", "label": "4-Panel Sliding", "kg": 16},
    ],
    "structural": [{"id": "str_g", "label": "Frameless Spider Glass Wall", "kg": 12}],
    "acp": [{"id": "acp_g", "label": "ACP Cladding", "kg": 5}],
    "balustrade": [{"id": "bal_g", "label": "Glass Balustrade", "kg": 6}],
    "shower": [{"id": "shw_g", "label": "Shower Cubicle", "kg": 8}],
}

SUBMAP = {}
for _pid, _subs in SUBS.items():
    for _s in _subs:
        SUBMAP[_s["id"]] = {**_s, "productId": _pid}

HW_ITEMS_DEF = [
    {"id": "hw1", "name": "Window Handle", "unit": "piece", "p": 5000},
    {"id": "hw2", "name": "Window Friction Stay", "unit": "piece", "p": 7000},
    {"id": "hw3", "name": "Casement Lock", "unit": "piece", "p": 4500},
    {"id": "hw4", "name": "Espagnolette Lock", "unit": "set", "p": 18000},
    {"id": "hw5", "name": "Sliding Handle", "unit": "piece", "p": 4500},
    {"id": "hw6", "name": "Sliding Lock Set", "unit": "set", "p": 8500},
    {"id": "hw7", "name": "Sliding Roller", "unit": "piece", "p": 3500},
    {"id": "hw8", "name": "Door Lock Set", "unit": "set", "p": 52000},
    {"id": "hw9", "name": "Door Hinge Pair", "unit": "pair", "p": 9500},
    {"id": "hw10", "name": "Door Handle Set", "unit": "set", "p": 14000},
    {"id": "hw11", "name": "Door Closer", "unit": "unit", "p": 24000},
    {"id": "hw12", "name": "CW/ACP Bracket Set", "unit": "set", "p": 27000},
    {"id": "hw13", "name": "ACP Rivet Set", "unit": "set", "p": 4000},
    {"id": "hw14", "name": "Spider Fitting 4-way", "unit": "piece", "p": 38000},
    {"id": "hw15", "name": "Balustrade Spigot SS316", "unit": "piece", "p": 19500},
    {"id": "hw16", "name": "Glass Clamp", "unit": "piece", "p": 10500},
    {"id": "hw17", "name": "Shower Hinge 180deg", "unit": "piece", "p": 32000},
    {"id": "hw18", "name": "Shower Handle", "unit": "pair", "p": 16000},
    {"id": "hw19", "name": "Shower Seal", "unit": "set", "p": 6500},
]

HW_KITS_DEF = {
    "etw_fixed": [], "etw_single": [{"id": "hw1", "q": 1}, {"id": "hw2", "q": 2}, {"id": "hw3", "q": 1}],
    "etw_double": [{"id": "hw1", "q": 2}, {"id": "hw2", "q": 4}, {"id": "hw4", "q": 1}],
    "etw_s2": [{"id": "hw5", "q": 2}, {"id": "hw6", "q": 1}, {"id": "hw7", "q": 4}],
    "etw_s3": [{"id": "hw5", "q": 3}, {"id": "hw6", "q": 2}, {"id": "hw7", "q": 4}],
    "etw_s4": [{"id": "hw5", "q": 4}, {"id": "hw6", "q": 2}, {"id": "hw7", "q": 8}],
    "ctw_fixed": [], "ctw_single": [{"id": "hw1", "q": 1}, {"id": "hw2", "q": 2}, {"id": "hw3", "q": 1}],
    "ctw_double": [{"id": "hw1", "q": 2}, {"id": "hw2", "q": 4}, {"id": "hw4", "q": 1}],
    "ctw_s2": [{"id": "hw5", "q": 2}, {"id": "hw6", "q": 1}, {"id": "hw7", "q": 4}],
    "ctw_s3": [{"id": "hw5", "q": 3}, {"id": "hw6", "q": 2}, {"id": "hw7", "q": 4}],
    "ctw_s4": [{"id": "hw5", "q": 4}, {"id": "hw6", "q": 2}, {"id": "hw7", "q": 8}],
    "etd_single": [{"id": "hw8", "q": 1}, {"id": "hw9", "q": 3}, {"id": "hw10", "q": 1}, {"id": "hw11", "q": 1}],
    "etd_double": [{"id": "hw8", "q": 2}, {"id": "hw9", "q": 6}, {"id": "hw10", "q": 2}, {"id": "hw11", "q": 2}],
    "etd_s2": [{"id": "hw5", "q": 2}, {"id": "hw6", "q": 1}, {"id": "hw7", "q": 4}],
    "etd_s3": [{"id": "hw5", "q": 3}, {"id": "hw6", "q": 2}, {"id": "hw7", "q": 4}],
    "etd_s4": [{"id": "hw5", "q": 4}, {"id": "hw6", "q": 2}, {"id": "hw7", "q": 8}],
    "ctd_single": [{"id": "hw8", "q": 1}, {"id": "hw9", "q": 3}, {"id": "hw10", "q": 1}, {"id": "hw11", "q": 1}],
    "ctd_double": [{"id": "hw8", "q": 2}, {"id": "hw9", "q": 6}, {"id": "hw10", "q": 2}, {"id": "hw11", "q": 2}],
    "ctd_s2": [{"id": "hw5", "q": 2}, {"id": "hw6", "q": 1}, {"id": "hw7", "q": 4}],
    "ctd_s3": [{"id": "hw5", "q": 3}, {"id": "hw6", "q": 2}, {"id": "hw7", "q": 4}],
    "ctd_s4": [{"id": "hw5", "q": 4}, {"id": "hw6", "q": 2}, {"id": "hw7", "q": 8}],
    "ctm_s2": [{"id": "hw5", "q": 2}, {"id": "hw6", "q": 1}, {"id": "hw7", "q": 4}],
    "ctm_s3": [{"id": "hw5", "q": 3}, {"id": "hw6", "q": 2}, {"id": "hw7", "q": 4}],
    "ctm_s4": [{"id": "hw5", "q": 4}, {"id": "hw6", "q": 2}, {"id": "hw7", "q": 8}],
    "etcw_g": [{"id": "hw12", "q": 1}], "ctcw_g": [{"id": "hw12", "q": 1}],
    "str_g": [{"id": "hw14", "q": 4}], "acp_g": [{"id": "hw12", "q": 1}, {"id": "hw13", "q": 1}],
    "bal_g": [{"id": "hw15", "q": 2}, {"id": "hw16", "q": 2}],
    "shw_g": [{"id": "hw17", "q": 2}, {"id": "hw18", "q": 1}, {"id": "hw19", "q": 1}],
}

SF_DEF = {
    "etw_fixed": 7, "etw_single": 11, "etw_double": 12, "etw_s2": 7, "etw_s3": 10, "etw_s4": 13,
    "ctw_fixed": 7, "ctw_single": 11, "ctw_double": 12, "ctw_s2": 7, "ctw_s3": 10, "ctw_s4": 13,
    "etd_single": 9, "etd_double": 10, "etd_s2": 8, "etd_s3": 11, "etd_s4": 14,
    "ctd_single": 9, "ctd_double": 10, "ctd_s2": 8, "ctd_s3": 11, "ctd_s4": 14,
    "ctm_s2": 10, "ctm_s3": 13, "ctm_s4": 16, "etcw_g": 14, "ctcw_g": 14,
    "str_g": 12, "acp_g": 5, "bal_g": 6, "shw_g": 8,
}

SUBFRAME_ELIGIBLE = [
    "etw_fixed", "etw_single", "etw_double", "etw_s2", "etw_s3", "etw_s4",
    "ctw_fixed", "ctw_single", "ctw_double", "ctw_s2", "ctw_s3", "ctw_s4",
    "etd_single", "etd_double", "etd_s2", "etd_s3", "etd_s4",
    "ctd_single", "ctd_double", "ctd_s2", "ctd_s3", "ctd_s4",
    "etcw_g", "ctcw_g", "ctm_s2", "ctm_s3", "ctm_s4",
]

MOSQ_ELIGIBLE = [
    "etw_single", "etw_double", "etw_s2", "etw_s3", "etw_s4",
    "ctw_single", "ctw_double", "ctw_s2", "ctw_s3", "ctw_s4",
    "etd_s2", "etd_s3", "etd_s4", "ctd_s2", "ctd_s3", "ctd_s4",
]

MOSQ_RATES_DEF = {k: 0 for k in MOSQ_ELIGIBLE}

SLIDING_MOSQ = [
    "etw_s2", "etw_s3", "etw_s4", "ctw_s2", "ctw_s3", "ctw_s4",
    "etd_s2", "etd_s3", "etd_s4", "ctd_s2", "ctd_s3", "ctd_s4",
]

ACP_DEF = [
    {"id": "ap1", "name": "3mm Composite Standard", "p": 12000},
    {"id": "ap2", "name": "4mm Composite Standard", "p": 17000},
    {"id": "ap3", "name": "4mm Composite Fire Rated A2", "p": 29000},
    {"id": "ap4", "name": "6mm Composite Heavy Duty", "p": 25000},
]

GC_DEF = {
    "types": [
        {"id": "single", "label": "Single Annealed", "isDGU": False},
        {"id": "tempered", "label": "Tempered / Toughened", "isDGU": False},
        {"id": "laminated", "label": "Laminated", "isDGU": False},
        {"id": "dgu", "label": "Double Glaze (DGU)", "isDGU": True},
    ],
    "thicknesses": {
        "single": ["6mm", "8mm", "10mm", "12mm"],
        "tempered": ["6mm", "8mm", "10mm", "12mm"],
        "laminated": ["10.38mm (5+5)", "12.76mm (6+6)", "16.76mm (8+8)"],
        "dgu": ["4+12A+4", "6+12A+6", "6+12A+8"],
    },
    "basePrices": {
        "single__6mm": 8500, "single__8mm": 10000, "single__10mm": 12500, "single__12mm": 15000,
        "tempered__6mm": 15000, "tempered__8mm": 18500, "tempered__10mm": 22000, "tempered__12mm": 27000,
        "laminated__10.38mm (5+5)": 24000, "laminated__12.76mm (6+6)": 29000, "laminated__16.76mm (8+8)": 36000,
        "dgu__4+12A+4": 28000, "dgu__6+12A+6": 34000, "dgu__6+12A+8": 38000,
    },
    "colours": [
        {"id": "clear", "label": "Clear", "premium": 0},
        {"id": "grey", "label": "Grey", "premium": 3500},
        {"id": "lowe", "label": "Low-E", "premium": 8000},
        {"id": "frosted", "label": "Frosted", "premium": 4500},
    ],
}

RATES_DEF = {
    "brandRates": {"EUROTEC": 3400, "CORTIZO": 3400, "DEFAULT": 3400},
    "gasketRate": 480, "fabRate": 7500, "installRate": 9500,
    "subframeRate": 7500, "sealantRate": 500,
}

SETTINGS_DEF = {
    "defaultMarkup": 100, "minMarkup": 70, "vatRate": 7.5, "validity": 14,
    "paymentTerms": "80% advance payment upon order confirmation. Balance of 20% payable upon agreed project milestones.",
    "tcs": (
        "1. Prices subject to change due to FX rate fluctuations.\n"
        "2. Quote validity subject to material availability.\n"
        "3. All works during normal business hours unless agreed otherwise.\n"
        "4. Excludes structural engineering, civil works or scaffolding unless stated.\n"
        "5. Title to goods remains with Interdec Facade until full payment received."
    ),
}

DEFAULT_CATALOG = {
    "products": PRODS,
    "subs": SUBS,
    "hwItems": HW_ITEMS_DEF,
    "hwKits": HW_KITS_DEF,
    "sf": SF_DEF,
    "mosqRates": MOSQ_RATES_DEF,
    "acpPanels": ACP_DEF,
    "gc": GC_DEF,
    "rates": RATES_DEF,
    "settings": SETTINGS_DEF,
}


def _r(value, nd=0):
    """JS-style Math.round(v * 10**nd) / 10**nd (half away from zero for positives)."""
    m = 10 ** nd
    return math.floor(value * m + 0.5) / m


def _f(x, default=0.0):
    try:
        v = float(x)
        return v if v == v else default  # NaN guard
    except (TypeError, ValueError):
        return default


def _prod_by_id(pid):
    for p in PRODS:
        if p["id"] == pid:
            return p
    return None


def auto_desc(item):
    """Customer-facing description generator (port of autoDesc)."""
    prod = _prod_by_id(item.get("product"))
    sub = SUBMAP.get(item.get("subTypeId") or "")
    brand = (prod or {}).get("brand", "")
    parts = [(sub or {}).get("label") or (prod or {}).get("label") or ""]
    for el in item.get("elements") or []:
        s2 = SUBMAP.get(el.get("subTypeId") or "")
        parts.append((s2 or {}).get("label") or el.get("subTypeId") or "")
    return ((brand + " ") if brand else "") + " + ".join(p for p in parts if p)


def glass_label(item, gc=None):
    g = gc or GC_DEF
    if not item.get("glassTypeId"):
        return "N/A"
    t = next((x for x in g["types"] if x["id"] == item.get("glassTypeId")), None)
    if not t:
        return "N/A"

    def cname(cid):
        c = next((c for c in g["colours"] if c["id"] == cid), None)
        return c["label"] if c else "N/A"

    if t["isDGU"]:
        return f"{t['label']} {item.get('glassThickness')} Out:{cname(item.get('glassDguOuter'))}/In:{cname(item.get('glassDguInner'))}"
    return f"{t['label']} {item.get('glassThickness')} - {cname(item.get('glassColour'))}"


def calc_bom_single(item, rates=None, gc=None, acp_panels=None, hw_items=None, hw_kits=None, sf=None, mosq_rates=None):
    """Port of calcBOMSingle — dimensions in mm (length in m for LM products)."""
    prod = _prod_by_id(item.get("product"))
    is_lm = bool(prod and prod.get("isLm"))
    rates = rates or RATES_DEF
    gc = gc or GC_DEF
    acp_panels = acp_panels if acp_panels is not None else ACP_DEF
    hw_items = hw_items if hw_items is not None else HW_ITEMS_DEF
    hw_kits = hw_kits if hw_kits is not None else HW_KITS_DEF
    sf_map = sf or SF_DEF
    mosq_map = mosq_rates if mosq_rates is not None else MOSQ_RATES_DEF

    W = _f(item.get("length")) if is_lm else _f(item.get("width")) / 1000.0
    H = _f(item.get("height")) / 1000.0
    try:
        qty = max(1, int(float(item.get("qty") or 1)))
    except (TypeError, ValueError):
        qty = 1

    area = _r(W * H * qty, 4)
    gasket_lm = _r((5 * W + 5 * H) * qty, 3)
    kg_factor = _f(sf_map.get(item.get("subTypeId")), 0)
    total_kg = _r(area * kg_factor, 3)
    brand = (prod or {}).get("brand") or "DEFAULT"
    brand_rates = rates.get("brandRates") or RATES_DEF["brandRates"]
    p_rate = float(brand_rates[brand]) if brand_rates.get(brand) is not None else 3400.0
    profile_cost = round(total_kg * p_rate)

    is_acp = item.get("product") == "acp"
    m_rate = 0.0
    if is_acp:
        if item.get("ovGlassRate") is not None:
            m_rate = _f(item.get("ovGlassRate"))
        else:
            for p in acp_panels:
                if p["id"] == item.get("acpPanelId"):
                    m_rate = float(p["p"])
    elif item.get("glassTypeId") and item.get("glassThickness"):
        base = (gc.get("basePrices") or {}).get(f"{item.get('glassTypeId')}__{item.get('glassThickness')}", 0)
        gtype = next((t for t in gc["types"] if t["id"] == item.get("glassTypeId")), None)
        is_dgu = bool(gtype and gtype["isDGU"])

        def cp(cid):
            c = next((c for c in gc["colours"] if c["id"] == cid), None)
            return float(c["premium"]) if c else 0.0

        m_rate = base + cp(item.get("glassDguOuter")) + cp(item.get("glassDguInner")) if is_dgu else base + cp(item.get("glassColour"))

    glass_cost = round(area * m_rate)
    gasket_cost = round(gasket_lm * _f(rates.get("gasketRate"), 480))

    kit = (hw_kits.get(item.get("subTypeId")) or []) if isinstance(hw_kits, dict) else []
    hw_index = {h["id"]: h for h in hw_items}
    kit_unit = sum(_f(hw_index[ki["id"]]["p"]) * _f(ki.get("q", 0)) for ki in kit if ki.get("id") in hw_index)
    hw_cost = round(kit_unit * W * qty) if is_lm else round(kit_unit * qty)

    fab_cost = round(area * _f(rates.get("fabRate"), 7500))
    inst_cost = round(area * _f(rates.get("installRate"), 9500))

    sub_type = item.get("subTypeId")
    mosq_rate = 0.0
    if item.get("hasMosq") and sub_type in MOSQ_ELIGIBLE:
        mosq_rate = _f((mosq_map or {}).get(sub_type), 0)
    mosq_area = area * 0.5 if sub_type in SLIDING_MOSQ else area
    mosq_cost = round(mosq_area * mosq_rate)

    sf_perim_lm = _r((2 * W + 2 * H) * qty, 3)
    sf_rate = _f(rates.get("subframeRate"), 7500) if (item.get("hasSubframe") and sub_type in SUBFRAME_ELIGIBLE) else 0.0
    subframe_cost = round(sf_perim_lm * sf_rate)

    # QUIRK 1: sealant follows subtype eligibility only, not the hasSubframe flag
    sealant_lm = _r((4 * W + 4 * H) * qty, 3) if sub_type in SUBFRAME_ELIGIBLE else 0.0
    sealant_rate = _f(rates.get("sealantRate"), 500)
    sealant_cost = round(sealant_lm * sealant_rate)

    total = profile_cost + glass_cost + gasket_cost + hw_cost + fab_cost + inst_cost + mosq_cost + subframe_cost + sealant_cost

    return {
        "W": W, "H": H, "qty": qty, "area": area, "gasketLm": gasket_lm,
        "totalKg": total_kg, "pRate": p_rate, "kgFactor": kg_factor, "mRate": m_rate,
        "glassCost": glass_cost, "gasketCost": gasket_cost, "hwCost": hw_cost,
        "fabCost": fab_cost, "instCost": inst_cost, "profileCost": profile_cost,
        "mosqCost": mosq_cost, "mosqRate": mosq_rate,
        "sfPerimLm": sf_perim_lm, "sfRate": sf_rate, "subframeCost": subframe_cost,
        "sealantLm": sealant_lm, "sealantRate": sealant_rate, "sealantCost": sealant_cost,
        "kitUnit": round(kit_unit), "total": total,
    }


_MERGE_KEYS = ["profileCost", "glassCost", "gasketCost", "hwCost", "fabCost", "instCost",
               "mosqCost", "sealantCost", "total", "totalKg", "area", "gasketLm",
               "sfPerimLm", "sealantLm"]


def calc_bom(item, rates=None, gc=None, acp_panels=None, hw_items=None, hw_kits=None, sf=None, mosq_rates=None):
    """Port of calcBOM — composite items (with elements) merge child BOMs.

    QUIRK 2: composite subframe is 1.5 x (W + H) per element x qty (shared edges).
    """
    elements = item.get("elements") or []
    if len(elements) > 0:
        base = calc_bom_single(item, rates, gc, acp_panels, hw_items, hw_kits, sf, mosq_rates)
        extras = [calc_bom_single({**el, "qty": item.get("qty") or 1}, rates, gc, acp_panels, hw_items, hw_kits, sf, mosq_rates) for el in elements]
        merged = dict(base)
        for ex in extras:
            for k in _MERGE_KEYS:
                merged[k] = (merged.get(k) or 0) + (ex.get(k) or 0)

        sub_type = item.get("subTypeId")
        if item.get("hasSubframe") and sub_type in SUBFRAME_ELIGIBLE:
            try:
                qty2 = max(1, int(float(item.get("qty") or 1)))
            except (TypeError, ValueError):
                qty2 = 1
            all_els = [item] + list(elements)
            total_sf_lm = 0.0
            for el in all_els:
                w2 = _f(el.get("width")) / 1000.0 if _f(el.get("width")) > 0 else _f(el.get("length"))
                h2 = _f(el.get("height")) / 1000.0
                total_sf_lm += (1.5 * w2 + 1.5 * h2) * qty2
            total_sf_lm = _r(total_sf_lm, 3)
            sf_r = _f((rates or RATES_DEF).get("subframeRate"), 7500)
            new_sf_cost = round(total_sf_lm * sf_r)
            merged["subframeCost"] = new_sf_cost
            merged["sfRate"] = sf_r
            merged["sfPerimLm"] = total_sf_lm
            merged["total"] = merged["total"] - base["subframeCost"] + new_sf_cost
        else:
            merged["subframeCost"] = 0

        merged["isComposite"] = True
        merged["elementBOMs"] = [base] + extras
        return merged
    return calc_bom_single(item, rates, gc, acp_panels, hw_items, hw_kits, sf, mosq_rates)


def calc_totals(items, markup=0, vat_rate=0, rates=None, gc=None, acp_panels=None,
                hw_items=None, hw_kits=None, sf=None, mosq_rates=None):
    """Port of calcTotals — cost, markup amount, subtotal, VAT, grand total.

    Returns per-item enriched copies (bom attached) plus revision-level totals.
    """
    items = items or []
    rates = dict(rates or RATES_DEF)
    enriched = []
    for i in items:
        it = deepcopy(i)
        it["bom"] = calc_bom(it, rates, gc, acp_panels, hw_items, hw_kits, sf, mosq_rates)
        it["desc"] = auto_desc(it)
        it["glassLabel"] = glass_label(it, gc)
        enriched.append(it)
    cost = sum((it["bom"]["total"] or 0) for it in enriched)
    mk_amt = round(cost * _f(markup) / 100.0)
    sub = cost + mk_amt
    vat = round(sub * _f(vat_rate) / 100.0)
    return {
        "items": enriched,
        "cost": cost,
        "mkAmt": mk_amt,
        "sub": sub,
        "vat": vat,
        "total": sub + vat,
    }


def next_quote_number(existing_numbers, year=None):
    """Server-side IDF-YYYY-NNN generator (per-year max + 1 — fixes audit R2)."""
    import datetime
    yr = year or datetime.date.today().year
    prefix = f"IDF-{yr}-"
    max_n = 0
    for num in existing_numbers or []:
        if num and str(num).startswith(prefix):
            try:
                max_n = max(max_n, int(str(num)[len(prefix):]))
            except ValueError:
                continue
    return f"{prefix}{max_n + 1:03d}"

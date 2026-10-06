"""Pricing engine tests — validate the port against the audited Table 5 spec.

Run:  cd /home/z/my-project/interdec-platform/backend && python3 -m pytest tests/test_pricing.py -v
(or)  python3 tests/test_pricing.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import pricing
from app.routers.quotes import _clamp_markup


GOLDEN_ITEM = {
    "id": "it1", "product": "et_window", "subTypeId": "etw_single",
    "width": 1200, "height": 1500, "qty": 10,
    "glassTypeId": "tempered", "glassThickness": "8mm", "glassColour": "clear",
    "hasMosq": False, "hasSubframe": False, "elements": [],
}


def test_golden_case_full_quote():
    """Audited E2E reference: cost N1,666,000 -> +100% markup -> 7.5% VAT -> N3,581,900."""
    t = pricing.calc_totals([GOLDEN_ITEM], 100, 7.5)
    assert t["cost"] == 1_666_000
    assert t["mkAmt"] == 1_666_000
    assert t["sub"] == 3_332_000
    assert t["vat"] == 249_900
    assert t["total"] == 3_581_900


def test_golden_case_components():
    bom = pricing.calc_bom(GOLDEN_ITEM)
    # area = 1.2m x 1.5m x 10 = 18 m2
    assert bom["area"] == 18.0
    # profile: 18 m2 x 11 kg/m2 x N3,400/kg = N673,200
    assert bom["totalKg"] == 198.0
    assert bom["profileCost"] == 673_200
    # glass: 18 m2 x (N18,500 tempered 8mm + N0 clear) = N333,000
    assert bom["mRate"] == 18_500
    assert bom["glassCost"] == 333_000
    # gasket: (5x1.2 + 5x1.5) x 10 = 135 LM x N480 = N64,800
    assert bom["gasketLm"] == 135.0
    assert bom["gasketCost"] == 64_800
    # hardware: (5000 + 2x7000 + 4500) = N23,500/unit x 10 = N235,000
    assert bom["kitUnit"] == 23_500
    assert bom["hwCost"] == 235_000
    # fabrication: 18 x N7,500 = N135,000
    assert bom["fabCost"] == 135_000
    # installation: 18 x N9,500 = N171,000
    assert bom["instCost"] == 171_000
    # subframe not selected -> zero
    assert bom["subframeCost"] == 0
    # QUIRK 1: sealant charged for eligible subtype even without subframe:
    # (4x1.2 + 4x1.5) x 10 = 108 LM x N500 = N54,000
    assert bom["sealantLm"] == 108.0
    assert bom["sealantCost"] == 54_000
    assert bom["total"] == 1_666_000


def test_subframe_charged_when_selected():
    item = dict(GOLDEN_ITEM, hasSubframe=True)
    bom = pricing.calc_bom(item)
    # subframe: (2x1.2 + 2x1.5) x 10 = 54 LM x N7,500 = N405,000
    assert bom["sfPerimLm"] == 54.0
    assert bom["subframeCost"] == 405_000
    # total grows by exactly the subframe amount
    assert bom["total"] == 1_666_000 + 405_000


def test_dgu_sums_both_colour_premiums():
    item = {
        "id": "x", "product": "et_cw", "subTypeId": "etcw_g",
        "width": 3000, "height": 2400, "qty": 1,
        "glassTypeId": "dgu", "glassThickness": "6+12A+6",
        "glassDguOuter": "lowe", "glassDguInner": "clear",
        "hasMosq": False, "hasSubframe": False, "elements": [],
    }
    bom = pricing.calc_bom(item)
    # DGU rate = 34,000 + Low-E 8,000 + Clear 0 = N42,000/m2
    assert bom["mRate"] == 42_000


def test_acp_panel_price_and_override():
    base = {"id": "x", "product": "acp", "subTypeId": "acp_g", "width": 2000, "height": 3000,
            "qty": 1, "hasMosq": False, "hasSubframe": False, "elements": [],
            "acpPanelId": "ap2"}
    assert pricing.calc_bom(base)["mRate"] == 17_000  # 4mm Composite Standard
    assert pricing.calc_bom(dict(base, ovGlassRate=21000))["mRate"] == 21_000


def test_sliding_mosquito_half_area():
    item = dict(GOLDEN_ITEM, subTypeId="etw_s2", hasMosq=True)
    item["product"] = "et_window"
    rates = {"brandRates": {"EUROTEC": 3400, "CORTIZO": 3400, "DEFAULT": 3400},
             "gasketRate": 480, "fabRate": 7500, "installRate": 9500,
             "subframeRate": 7500, "sealantRate": 500}
    bom = pricing.calc_bom(item, rates=rates, mosq_rates={"etw_s2": 4000})
    # sliding: 50% of area charged -> 9 m2 x N4,000 = N36,000
    assert bom["mosqCost"] == 36_000


def test_lm_product_balustrade():
    """LM products: length in metres, hardware scales by width."""
    item = {"id": "x", "product": "balustrade", "subTypeId": "bal_g", "length": 5,
            "height": 1200, "qty": 1, "hasMosq": False, "hasSubframe": False, "elements": []}
    bom = pricing.calc_bom(item)
    # area = 5m x 1.2m = 6 m2, kg factor 6 -> 36 kg x 3400 = N122,400
    assert bom["profileCost"] == 122_400
    # kit bal_g = 2x19,500 + 2x10,500 = N60,000, scaled by W=5 -> N300,000
    assert bom["hwCost"] == 300_000


def test_composite_subframe_shared_edges():
    """QUIRK 2: composite subframe = 1.5 x (W + H) per element x qty."""
    item = {
        "id": "x", "product": "et_window", "subTypeId": "etw_s2",
        "width": 1200, "height": 1500, "qty": 2,
        "glassTypeId": "tempered", "glassThickness": "8mm", "glassColour": "clear",
        "hasMosq": False, "hasSubframe": True,
        "elements": [
            {"id": "e1", "product": "et_window", "subTypeId": "etw_fixed", "width": 600, "height": 1500},
            {"id": "e2", "product": "et_window", "subTypeId": "etw_fixed", "width": 600, "height": 1500},
        ],
    }
    bom = pricing.calc_bom(item)
    # parent 1.2x1.5 + two elements 0.6x1.5 -> sum 1.5*(1.2+1.5)*2 + 2 x 1.5*(0.6+1.5)*2
    # = 8.1 + 12.6 = 20.7 LM x N7,500 = N155,250
    assert abs(bom["sfPerimLm"] - 20.7) < 1e-9
    assert bom["subframeCost"] == 155_250
    assert bom["isComposite"] is True
    assert len(bom["elementBOMs"]) == 3


def test_markup_floor_clamp():
    catalog = {"settings": dict(pricing.SETTINGS_DEF)}  # minMarkup 70
    assert _clamp_markup(100, catalog) == 100
    assert _clamp_markup(50, catalog) == 70
    assert _clamp_markup(None, catalog) == 100  # default


def test_quote_numbering_year_rollover_and_gaps():
    # fixes audit R2: server-side per-year max+1, deletions never duplicate
    assert pricing.next_quote_number([], 2026) == "IDF-2026-001"
    assert pricing.next_quote_number(["IDF-2026-001"], 2026) == "IDF-2026-002"
    # 002 deleted -> next is still 004, never a duplicate of the deleted number
    assert pricing.next_quote_number(["IDF-2026-001", "IDF-2026-003"], 2026) == "IDF-2026-004"
    # other years ignored
    assert pricing.next_quote_number(["IDF-2025-009", "IDF-2026-001"], 2026) == "IDF-2026-002"


def test_desc_and_glass_labels():
    assert pricing.auto_desc(GOLDEN_ITEM) == "EUROTEC Single Casement"
    assert pricing.glass_label(GOLDEN_ITEM) == "Tempered / Toughened 8mm - Clear"
    dgu = dict(GOLDEN_ITEM, glassTypeId="dgu", glassThickness="6+12A+6",
               glassDguOuter="lowe", glassDguInner="frosted")
    assert pricing.glass_label(dgu) == "Double Glaze (DGU) 6+12A+6 Out:Low-E/In:Frosted"


def test_totals_multiple_items_aggregate():
    t = pricing.calc_totals([GOLDEN_ITEM, dict(GOLDEN_ITEM, id="it2", qty=1)], 70, 7.5)
    single = pricing.calc_totals([GOLDEN_ITEM], 70, 7.5)
    assert t["cost"] == single["cost"] + 166_600  # one more unit at same spec
    assert t["total"] == round((t["cost"] + round(t["cost"] * 0.7)) * 1.075)


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for fn in fns:
        try:
            fn()
            print(f"  PASS {fn.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"  FAIL {fn.__name__}: {e}")
    print(f"\n{len(fns) - failed}/{len(fns)} passed")
    sys.exit(1 if failed else 0)

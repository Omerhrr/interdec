"""Money across the platform: currency conversion, shipment landed cost, vendor
payment balances and project budget vs actual. One place so the project page,
reports, exports and emails all agree.

Exchange rates are stored as "1 unit = x USD" (settings.fxRates).
"""
from . import models

STATUS_ORDER = ["order_placed", "under_production", "in_transit", "completed"]


def fx_rates(db) -> dict:
    from .routers.settings import _out, _row
    return _out(_row(db))["rates"]


class Money:
    def __init__(self, db):
        self.db = db
        self.rates = fx_rates(db)

    def usd(self, amount, currency) -> float:
        return float(amount or 0) * float(self.rates.get((currency or "USD").upper(), 1) or 1)

    def ngn(self, amount, currency) -> float:
        if (currency or "").upper() == "NGN":
            return float(amount or 0)
        return self.usd(amount, currency) / float(self.rates.get("NGN") or 0.00065)

    # --- shipments ---------------------------------------------------------
    def goods_usd(self, s) -> float:
        return self.usd(s.value, s.currency)

    def cost_usd(self, c) -> float:
        return self.usd((c or {}).get("total"), (c or {}).get("currency")) if c else 0.0

    def landed_usd(self, s) -> float:
        return self.goods_usd(s) + self.cost_usd(s.shipping_cost) + self.cost_usd(s.clearing_cost)

    def landed_ngn(self, s) -> float:
        return self.landed_usd(s) / float(self.rates.get("NGN") or 0.00065)


# ---------------------------------------------------------------------------
# vendor payments (stored on the shipment, in the shipment's currency)
# ---------------------------------------------------------------------------

def vendor_paid(s) -> float:
    return round(sum(float(p.get("amount") or 0) for p in (s.vendor_payments or [])), 2)


def vendor_balance(s) -> float:
    return round(max(float(s.value or 0) - vendor_paid(s), 0.0), 2)


def vendor_status(s) -> str:
    """unpaid | part | paid | n/a (no order value)"""
    if not float(s.value or 0):
        return "n/a"
    paid = vendor_paid(s)
    if paid <= 0:
        return "unpaid"
    return "paid" if vendor_balance(s) <= 0.005 else "part"


def payment_due(s) -> bool:
    """Vendor should be fully paid by now under the agreed terms."""
    if vendor_status(s) in ("paid", "n/a"):
        return False
    terms = (s.payment_terms or "").lower()
    stage = STATUS_ORDER.index(s.status) if s.status in STATUS_ORDER else 0
    if "before" in terms:
        return stage >= 1   # production started: pay before it ships
    if "after" in terms:
        return stage >= 2   # shipped: balance is now due
    return False


# ---------------------------------------------------------------------------
# projects: budget vs actual
# ---------------------------------------------------------------------------

def project_budget(db, p, money: Money | None = None, quotes=None, shipments=None) -> dict:
    """Contract value from won quotes vs what has actually been spent importing goods for it.

    All figures in naira. Quote figures use each quote's locked exchange rate;
    shipments use today's rates (as everywhere else in ImportFlow)."""
    money = money or Money(db)
    if quotes is None:
        quotes = db.query(models.Quote).filter(models.Quote.project_id == p.id).all()
    if shipments is None:
        shipments = db.query(models.Shipment).filter(models.Shipment.project_id == p.id).all()
    won, pending = [], []
    for q in quotes:
        rev = (db.query(models.QuoteRevision).filter(models.QuoteRevision.quote_id == q.id)
               .order_by(models.QuoteRevision.rev.desc()).first())
        if not rev:
            continue
        rate = float(rev.fx_rate or 1)
        row = {"id": q.id, "number": q.number, "client": q.client_name, "status": rev.status,
               "currency": rev.currency or "NGN", "total": float(rev.total or 0),
               "subNgn": round(float(rev.sub or 0) * rate, 2), "costNgn": round(float(rev.cost or 0) * rate, 2)}
        (won if rev.status == "won" else pending if rev.status in ("draft", "sent") else []).append(row)
    contract = round(sum(r["subNgn"] for r in won), 2)
    est_cost = round(sum(r["costNgn"] for r in won), 2)
    spent = round(sum(money.landed_ngn(s) for s in shipments), 2)
    goods = round(sum(money.ngn(s.value, s.currency) for s in shipments), 2)
    shipping = round(sum(money.ngn((s.shipping_cost or {}).get("total"), (s.shipping_cost or {}).get("currency")) for s in shipments if s.shipping_cost), 2)
    clearing = round(sum(money.ngn((s.clearing_cost or {}).get("total"), (s.clearing_cost or {}).get("currency")) for s in shipments if s.clearing_cost), 2)
    vendor_paid_ngn = round(sum(money.ngn(vendor_paid(s), s.currency) for s in shipments), 2)
    vendor_owed_ngn = round(sum(money.ngn(vendor_balance(s), s.currency) for s in shipments), 2)
    margin = round(contract - spent, 2)
    return {
        "projectId": p.id, "contract": contract, "estimatedCost": est_cost, "spent": spent,
        "goods": goods, "shipping": shipping, "clearing": clearing,
        "vendorPaid": vendor_paid_ngn, "vendorOwed": vendor_owed_ngn,
        "margin": margin, "marginPct": round(margin / contract * 100, 1) if contract else None,
        "usedPct": round(spent / contract * 100, 1) if contract else None,
        "pendingValue": round(sum(r["subNgn"] for r in pending), 2),
        "wonQuotes": won, "pendingQuotes": pending, "shipments": len(shipments),
        "openShipments": len([s for s in shipments if s.status != "completed"]),
    }

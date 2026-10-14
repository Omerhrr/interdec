"""Email notifications people opt into (Settings → Email notifications):

  statusChanges   a shipment moves to a new stage (Under Production, In Transit, Completed)
  quoteOutcomes   a quote is marked won or lost
  payablesDigest  Monday-morning summary of what's owed (vendor balances, unpaid shipping/clearing)

Defaults when a person hasn't chosen: digest on for ImportFlow admins, quote
outcomes on for platform admins, status changes off (they can be chatty).
"""
import html as _html
import os
from datetime import datetime, timedelta

from . import models, mailer, finance, auth

PREF_KEYS = ("statusChanges", "quoteOutcomes", "payablesDigest")
STATUS_LABELS = {"order_placed": "Order Placed", "under_production": "Under Production",
                 "in_transit": "In Transit", "completed": "Completed"}


def defaults_for(u: models.User) -> dict:
    return {"statusChanges": False, "quoteOutcomes": u.platform_role == "admin",
            "payablesDigest": auth.importflow_role(u) == "admin" and _has_if(u)}


def _has_if(u):
    return u.platform_role == "admin" or bool(((u.apps or {}).get("importflow") or {}).get("access"))


def prefs(u: models.User) -> dict:
    p = defaults_for(u)
    p.update({k: bool(v) for k, v in (u.notify_prefs or {}).items() if k in PREF_KEYS})
    return p


def recipients(db, key: str, exclude: models.User | None = None, need=None) -> list[str]:
    out = []
    for u in db.query(models.User).filter(models.User.active == True).all():  # noqa: E712
        if exclude is not None and u.id == exclude.id:
            continue
        if need and not need(u):
            continue
        if prefs(u).get(key) and mailer.valid_email(u.email):
            out.append(u.email)
    return out


# ---------------------------------------------------------------------------
# layout shared by every notification
# ---------------------------------------------------------------------------

def card(title: str, lead: str, rows: list[tuple[str, str]], color="#2563eb", link="", link_label="Open in Interdec",
         table: tuple[list[str], list[list[str]]] | None = None, footer="") -> str:
    e = _html.escape
    trs = "".join(f'<tr><td style="padding:5px 12px 5px 0;color:#64748b;font-size:13px;white-space:nowrap">{e(k)}</td>'
                  f'<td style="padding:5px 0;font-size:13px;color:#0f172a;font-weight:600">{e(str(v or "—"))}</td></tr>' for k, v in rows)
    tbl = ""
    if table:
        head, body = table
        th = "".join(f'<th align="left" style="padding:6px 8px;font-size:11px;color:#fff;background:{color};text-transform:uppercase">{e(h)}</th>' for h in head)
        tb = "".join("<tr>" + "".join(f'<td style="padding:6px 8px;font-size:12.5px;border-bottom:1px solid #e2e8f0;color:#0f172a">{e(str(c))}</td>' for c in r) + "</tr>" for r in body)
        tbl = f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;margin-top:14px"><tr>{th}</tr>{tb}</table>'
    btn = (f'<p style="margin:20px 0 0"><a href="{e(link)}" style="background:{color};color:#fff;text-decoration:none;padding:10px 18px;'
           f'border-radius:8px;font-weight:700;font-size:14px;display:inline-block">{e(link_label)}</a></p>') if link else ""
    return f"""<!doctype html><html><body style="margin:0;background:#f1f5f9;font-family:Arial,Helvetica,sans-serif">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr><td align="center" style="padding:24px 12px">
<table role="presentation" width="100%" style="max-width:600px;background:#fff;border-radius:12px;overflow:hidden" cellpadding="0" cellspacing="0">
<tr><td style="background:{color};height:5px"></td></tr><tr><td style="padding:22px 26px">
<h1 style="margin:0 0 4px;font-size:19px;color:#0f172a">{e(title)}</h1>
<p style="margin:0 0 14px;font-size:14px;color:#334155">{e(lead)}</p>
<table role="presentation" cellpadding="0" cellspacing="0">{trs}</table>{tbl}{btn}</td></tr>
<tr><td style="padding:12px 26px;background:#f8fafc;font-size:11.5px;color:#64748b">{e(footer or "You get this because of your email notification settings in Interdec. Change them any time from the sidebar.")}</td></tr>
</table></td></tr></table></body></html>"""


def _url(path):
    base = mailer.config()["appUrl"]
    return f"{base}{path}" if base else ""


def _text(title, lead, rows, link=""):
    return f"{title}\n\n{lead}\n\n" + "\n".join(f"{k}: {v or '—'}" for k, v in rows) + (f"\n\nOpen: {link}" if link else "")


# ---------------------------------------------------------------------------
# events
# ---------------------------------------------------------------------------

def shipment_status_changed(db, s: models.Shipment, old: str, actor: models.User):
    to = recipients(db, "statusChanges", exclude=actor, need=_has_if)
    if not to:
        return
    vendor = db.query(models.Vendor).filter(models.Vendor.id == s.vendor_id).first() if s.vendor_id else None
    project = db.query(models.Project).filter(models.Project.id == s.project_id).first() if s.project_id else None
    new = STATUS_LABELS.get(s.status, s.status)
    title = f"{s.ref} is now {new}"
    lead = f"{actor.name} moved this shipment from {STATUS_LABELS.get(old, old)} to {new}."
    rows = [("Shipment", s.ref), ("Description", s.description), ("Vendor", vendor.name if vendor else ""),
            ("Project", project.name if project else "General stock"), ("ETA", s.eta), ("Value", f"{s.currency} {float(s.value or 0):,.2f}")]
    color = {"under_production": "#d97706", "in_transit": "#7c3aed", "completed": "#059669"}.get(s.status, "#2563eb")
    link = _url(f"/platform/importflow/shipments/{s.id}")
    mailer.send(db, to, title, card(title, lead, rows, color, link), _text(title, lead, rows, link),
                kind="notify.status", shipment_id=s.id)


def quote_outcome(db, q: models.Quote, rev: models.QuoteRevision, actor: models.User):
    to = recipients(db, "quoteOutcomes", exclude=actor, need=auth.has_quotes_access)
    if not to:
        return
    won = rev.status == "won"
    title = f"{q.number} {'won' if won else 'lost'}: {q.client_name or 'client'}"
    lead = f"{actor.name} marked this quote {'won' if won else 'lost'}." + (f" Note: {rev.status_note}" if rev.status_note else "")
    cur = rev.currency or "NGN"
    rows = [("Quote", f"{q.number} Rev.{rev.rev}"), ("Client", q.client_name), ("Sales person", q.sales_person),
            ("Total", f"{cur} {float(rev.total or 0):,.2f}"), ("Project", q.project_name)]
    link = _url(f"/platform/quotes/{q.id}")
    mailer.send(db, to, title, card(title, lead, rows, "#059669" if won else "#64748b", link), _text(title, lead, rows, link),
                kind=f"notify.quote_{rev.status}")


def payables_rows(db):
    money = finance.Money(db)
    vendors = {v.id: v.name for v in db.query(models.Vendor).all()}
    shippers = {s.id: s.name for s in db.query(models.Shipper).all()}
    agents = {a.id: a.name for a in db.query(models.ClearingAgent).all()}
    rows = []
    for s in db.query(models.Shipment).all():
        bal = finance.vendor_balance(s)
        if bal > 0.005 and s.value:
            rows.append({"ref": s.ref, "what": "Vendor", "to": vendors.get(s.vendor_id, ""), "amount": f"{s.currency} {bal:,.2f}",
                         "usd": money.usd(bal, s.currency), "due": finance.payment_due(s)})
        for label, c, who in (("Shipping", s.shipping_cost, shippers.get(s.shipper_id, "")),
                              ("Clearing", s.clearing_cost, agents.get(s.clearing_agent_id, ""))):
            if c and c.get("total") and not c.get("paid"):
                rows.append({"ref": s.ref, "what": label, "to": who, "amount": f"{c.get('currency')} {float(c['total']):,.2f}",
                             "usd": money.cost_usd(c), "due": True})
    rows.sort(key=lambda r: (not r["due"], -r["usd"]))
    return rows


def send_digest(db, to: list[str]) -> tuple[bool, str]:
    rows = payables_rows(db)
    total = sum(r["usd"] for r in rows)
    due = sum(r["usd"] for r in rows if r["due"])
    title = f"Payables this week: $ {total:,.0f} owed" if rows else "Payables this week: nothing owed"
    lead = (f"{len(rows)} unpaid item{'s' if len(rows) != 1 else ''}; $ {due:,.0f} of it is due now." if rows
            else "Every vendor, shipping and clearing invoice is paid.")
    table = (["Shipment", "For", "To", "Amount", "Due now"],
             [[r["ref"], r["what"], r["to"], r["amount"], "Yes" if r["due"] else ""] for r in rows[:40]]) if rows else None
    link = _url("/platform/importflow/reports")
    html = card(title, lead, [("Total owed", f"$ {total:,.0f}"), ("Due now", f"$ {due:,.0f}")], "#b45309", link,
                "Open reports", table)
    text = _text(title, lead, [(r["ref"], f'{r["what"]} · {r["to"]} · {r["amount"]}' + (" · DUE" if r["due"] else "")) for r in rows], link)
    return mailer.send(db, to, title, html, text, kind="notify.digest")


DIGEST_KEY = "payablesDigestLast"


def maybe_send_weekly_digest(db, now: datetime | None = None) -> bool:
    """Mondays from 08:00 (INTERDEC_TZ), once per ISO week."""
    from .eta_alerts import today
    if now is None:
        tz = os.environ.get("INTERDEC_TZ", "Africa/Lagos")
        try:
            from zoneinfo import ZoneInfo
            now = datetime.now(ZoneInfo(tz))
        except Exception:
            now = datetime.now()
    day = int(os.environ.get("INTERDEC_DIGEST_WEEKDAY", "0"))  # 0 = Monday
    if now.weekday() != day or now.hour < 8:
        return False
    week = f"{now.isocalendar()[0]}-W{now.isocalendar()[1]}"
    row = db.query(models.FacadeSetting).filter(models.FacadeSetting.key == DIGEST_KEY).first()
    if row and (row.value or {}).get("week") == week:
        return False
    to = recipients(db, "payablesDigest", need=_has_if)
    if to:
        ok, _ = send_digest(db, to)
        if not ok:
            db.commit()
            return False
    stamp = {"week": week, "sentTo": len(to)}
    if row:
        row.value = stamp
    else:
        db.add(models.FacadeSetting(key=DIGEST_KEY, value=stamp, updated=int(now.timestamp() * 1000)))
    db.commit()
    return bool(to)

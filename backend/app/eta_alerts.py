"""ETA email alerts for shipments.

Each shipment can carry alert settings (Shipment.eta_alerts):
    {"enabled": true, "recipients": ["a@x.com"], "before": [7, 3, 1],
     "onDay": true, "overdue": true, "onChange": true,
     "sent": {"before_3@2026-04-20": 1760000000000, ...}}

A background job (start_scheduler) checks every INTERDEC_ALERT_INTERVAL_MIN
minutes (default 30). "sent" keys include the ETA date, so each reminder goes
out once per ETA, and changing the ETA re-arms them. If the server was down on
the exact day, the closest reminder still due is sent on the next check
(without a burst of stale ones).
"""
import html as _html
import logging
import os
import re
import threading
import time
from datetime import date, datetime, timedelta

from . import models, mailer

log = logging.getLogger("interdec.eta")

DEFAULTS = {"enabled": False, "recipients": [], "before": [3, 1], "onDay": True, "overdue": True, "onChange": True, "sent": {}}
ALLOWED_BEFORE = (1, 2, 3, 5, 7, 14, 30)
STATUS_LABELS = {"order_placed": "Order Placed", "under_production": "Under Production",
                 "in_transit": "In Transit", "completed": "Completed"}
COMPANIES = {"facade": "Facade", "davinci": "Davinci", "doortec": "Doortec"}


def today() -> date:
    tz = os.environ.get("INTERDEC_TZ", "Africa/Lagos")
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo(tz)).date()
    except Exception:
        return date.today()


def parse_eta(v) -> date | None:
    """ISO (2026-04-20) or day-first (20/04/26, 20-04-2026)."""
    v = (v or "").strip()
    if not v:
        return None
    try:
        return date.fromisoformat(v[:10])
    except ValueError:
        pass
    m = re.match(r"^(\d{1,2})[/.-](\d{1,2})[/.-](\d{2}|\d{4})$", v)
    if not m:
        return None
    d, mo, y = int(m[1]), int(m[2]), int(m[3])
    y = 2000 + y if y < 100 else y
    try:
        return date(y, mo, d)
    except ValueError:
        return None


def settings_of(s: models.Shipment) -> dict:
    a = {**DEFAULTS, **(s.eta_alerts or {})}
    a["sent"] = dict(a.get("sent") or {})
    return a


def public_settings(s: models.Shipment) -> dict:
    a = settings_of(s)
    eta = parse_eta(s.eta)
    sent = sorted(((k, v) for k, v in a["sent"].items()), key=lambda kv: -kv[1])
    return {k: a[k] for k in ("enabled", "recipients", "before", "onDay", "overdue", "onChange")} | {
        "lastSent": [{"key": k.split("@")[0], "eta": k.split("@")[1] if "@" in k else "", "ts": v} for k, v in sent[:5]],
        "etaDate": eta.isoformat() if eta else None,
    }


def clean_settings(body: dict, current: dict) -> dict:
    """Validate an update from the UI. Raises ValueError with a readable message."""
    out = dict(current)
    if "enabled" in body:
        out["enabled"] = bool(body["enabled"])
    if "recipients" in body:
        rec = body["recipients"]
        if not isinstance(rec, list):
            raise ValueError("recipients must be a list of email addresses")
        rec = list(dict.fromkeys(str(r).strip().lower() for r in rec if str(r).strip()))
        bad = [r for r in rec if not mailer.valid_email(r)]
        if bad:
            raise ValueError(f"Not a valid email address: {bad[0]}")
        if len(rec) > 20:
            raise ValueError("At most 20 recipients per shipment")
        out["recipients"] = rec
    if "before" in body:
        b = body["before"]
        if not isinstance(b, list) or any(int(x) not in ALLOWED_BEFORE for x in b):
            raise ValueError(f"Reminder days must be from {list(ALLOWED_BEFORE)}")
        out["before"] = sorted({int(x) for x in b}, reverse=True)
    for k in ("onDay", "overdue", "onChange"):
        if k in body:
            out[k] = bool(body[k])
    if out["enabled"] and not out["recipients"]:
        raise ValueError("Add at least one email address to turn alerts on")
    return out


# ---------------------------------------------------------------------------
# what is due
# ---------------------------------------------------------------------------

def due(s: models.Shipment, on: date | None = None) -> list[tuple[str, int]]:
    """[(kind, days_to_eta)] reminders that should go out now. kind: before_N | on_day | overdue."""
    a = settings_of(s)
    eta = parse_eta(s.eta)
    if not a["enabled"] or not a["recipients"] or not eta or s.status == "completed":
        return []
    on = on or today()
    days = (eta - on).days
    tag = eta.isoformat()
    out = []
    if days > 0:
        # closest reminder window we're inside, if not sent yet
        windows = sorted(n for n in a["before"] if days <= n)
        if windows and f"before_{windows[0]}@{tag}" not in a["sent"]:
            out.append((f"before_{windows[0]}", days))
    elif days == 0:
        if a["onDay"] and f"on_day@{tag}" not in a["sent"]:
            out.append(("on_day", 0))
    elif a["overdue"] and f"overdue@{tag}" not in a["sent"]:
        out.append(("overdue", days))
    return out


def mark_sent(s: models.Shipment, kind: str):
    a = settings_of(s)
    eta = parse_eta(s.eta)
    tag = eta.isoformat() if eta else ""
    now = int(time.time() * 1000)
    a["sent"][f"{kind}@{tag}"] = now
    if kind.startswith("before_"):  # wider windows are now stale
        n = int(kind.split("_")[1])
        for m in a["before"]:
            if m > n:
                a["sent"].setdefault(f"before_{m}@{tag}", now)
    # keep the log small: only this ETA's keys plus the 20 most recent others
    keep = sorted(a["sent"].items(), key=lambda kv: -kv[1])[:20]
    a["sent"] = dict(keep)
    s.eta_alerts = a


# ---------------------------------------------------------------------------
# message
# ---------------------------------------------------------------------------

def _fmt(d: date | None) -> str:
    return d.strftime("%a %d %b %Y") if d else "not set"


def compose(db, s: models.Shipment, kind: str, days: int = 0, old_eta: str = "") -> tuple[str, str, str]:
    eta = parse_eta(s.eta)
    vendor = db.query(models.Vendor).filter(models.Vendor.id == s.vendor_id).first() if s.vendor_id else None
    shipper = db.query(models.Shipper).filter(models.Shipper.id == s.shipper_id).first() if s.shipper_id else None
    project = db.query(models.Project).filter(models.Project.id == s.project_id).first() if s.project_id else None
    ref = s.ref
    if kind.startswith("before_"):
        when = "tomorrow" if days == 1 else f"in {days} days"
        subject, lead, color = f"{ref} arrives {when} ({_fmt(eta)})", f"This shipment is due {when}.", "#2563eb"
    elif kind == "on_day":
        subject, lead, color = f"{ref} is due today", "This shipment is due to arrive today.", "#059669"
    elif kind == "overdue":
        late = -days
        subject = f"{ref} is overdue: ETA was {_fmt(eta)}"
        lead, color = f"This shipment was due {late} day{'s' if late != 1 else ''} ago and isn't marked as received yet.", "#dc2626"
    elif kind == "changed":
        subject = f"ETA changed for {ref}: {_fmt(parse_eta(old_eta)) if old_eta else 'not set'} → {_fmt(eta)}"
        lead, color = "The expected arrival date for this shipment has changed.", "#d97706"
    else:  # test
        subject, lead, color = f"Test: ETA alerts for {ref}", "This is a test. ETA reminders for this shipment will look like this.", "#475569"

    rows = [
        ("Shipment", ref), ("Description", s.description), ("ETA", _fmt(eta)),
        ("Status", STATUS_LABELS.get(s.status, s.status)), ("Company", COMPANIES.get(s.company_id, s.company_id)),
        ("Project", project.name if project else "General stock"), ("Vendor", vendor.name if vendor else ""),
        ("Shipper", shipper.name if shipper else "Not assigned"), ("Method", s.ship_method),
        ("Value", f"{s.currency or 'USD'} {float(s.value or 0):,.2f}"),
    ]
    if kind == "changed":
        rows.insert(2, ("Previous ETA", _fmt(parse_eta(old_eta)) if old_eta else "not set"))
    url = mailer.config()["appUrl"]
    link = f"{url}/platform/importflow/shipments/{s.id}" if url else ""
    e = _html.escape
    trs = "".join(f'<tr><td style="padding:6px 12px 6px 0;color:#64748b;font-size:13px;white-space:nowrap">{e(k)}</td>'
                  f'<td style="padding:6px 0;font-size:13px;color:#0f172a;font-weight:600">{e(str(v or "—"))}</td></tr>' for k, v in rows)
    btn = (f'<p style="margin:22px 0 0"><a href="{e(link)}" style="background:{color};color:#fff;text-decoration:none;'
           f'padding:10px 18px;border-radius:8px;font-weight:700;font-size:14px;display:inline-block">Open shipment</a></p>') if link else ""
    html = f"""<!doctype html><html><body style="margin:0;background:#f1f5f9;font-family:Arial,Helvetica,sans-serif">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr><td align="center" style="padding:24px 12px">
<table role="presentation" width="100%" style="max-width:560px;background:#fff;border-radius:12px;overflow:hidden" cellpadding="0" cellspacing="0">
<tr><td style="background:{color};height:5px"></td></tr>
<tr><td style="padding:24px 26px">
<div style="font-size:12px;color:#64748b;font-weight:700;letter-spacing:.6px;text-transform:uppercase">ImportFlow · ETA alert</div>
<h1 style="margin:6px 0 4px;font-size:20px;color:#0f172a">{e(subject)}</h1>
<p style="margin:0 0 16px;font-size:14px;color:#334155">{e(lead)}</p>
<table role="presentation" cellpadding="0" cellspacing="0">{trs}</table>{btn}
</td></tr>
<tr><td style="padding:14px 26px;background:#f8fafc;font-size:11.5px;color:#64748b">You're receiving this because your address is on the ETA alert list for {e(ref)}. Anyone with edit access can change the list on the shipment page.</td></tr>
</table></td></tr></table></body></html>"""
    text = f"{subject}\n\n{lead}\n\n" + "\n".join(f"{k}: {v or '—'}" for k, v in rows) + (f"\n\nOpen: {link}" if link else "")
    return subject, html, text


def send_alert(db, s: models.Shipment, kind: str, days: int = 0, old_eta: str = "", recipients=None) -> tuple[bool, str]:
    a = settings_of(s)
    subject, html, text = compose(db, s, kind, days, old_eta)
    return mailer.send(db, recipients or a["recipients"], subject, html, text, kind=f"eta.{kind}", shipment_id=s.id)


# ---------------------------------------------------------------------------
# the periodic check
# ---------------------------------------------------------------------------

def run_check(db, on: date | None = None) -> dict:
    sent = failed = 0
    rows = db.query(models.Shipment).filter(models.Shipment.status != "completed").all()
    for s in rows:
        for kind, days in due(s, on):
            ok, _ = send_alert(db, s, kind, days)
            if ok:
                mark_sent(s, kind)
                sent += 1
            else:
                failed += 1  # retried on the next check
        db.commit()
    return {"checked": len(rows), "sent": sent, "failed": failed}


_started = False


def start_scheduler(session_factory):
    """Background thread; one per process. Disabled with INTERDEC_DISABLE_SCHEDULER=1 (tests)."""
    global _started
    if _started or os.environ.get("INTERDEC_DISABLE_SCHEDULER") == "1":
        return
    _started = True
    try:
        every = max(5, int(os.environ.get("INTERDEC_ALERT_INTERVAL_MIN", "30")))
    except ValueError:
        every = 30

    def loop():
        time.sleep(20)  # let the app finish starting
        while True:
            db = session_factory()
            try:
                r = run_check(db)
                if r["sent"] or r["failed"]:
                    log.info("ETA alerts: %s", r)
                from . import notify_mail
                if notify_mail.maybe_send_weekly_digest(db):
                    log.info("Weekly payables digest sent")
            except Exception:  # never let the loop die
                log.exception("ETA alert check failed")
                db.rollback()
            finally:
                db.close()
            time.sleep(every * 60)

    threading.Thread(target=loop, name="eta-alerts", daemon=True).start()

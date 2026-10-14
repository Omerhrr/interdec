"""Outgoing email over SMTP, configured with environment variables:

  INTERDEC_SMTP_HOST      e.g. smtp.gmail.com / smtp.zoho.com / smtp.office365.com
  INTERDEC_SMTP_PORT      587 (STARTTLS, default) or 465 (SSL)
  INTERDEC_SMTP_USER      login (usually the mailbox address)
  INTERDEC_SMTP_PASSWORD  password or app password
  INTERDEC_SMTP_FROM      "Interdec <alerts@yourdomain.com>" (defaults to the user)
  INTERDEC_APP_URL        public address of the app, for links in emails

Every attempt is written to the email log (sent, failed or not configured), so
nothing disappears silently when email isn't set up yet.
"""
import os
import smtplib
import ssl
import time
import uuid
from email.message import EmailMessage
from email.utils import formataddr, parseaddr

from . import models


def config() -> dict:
    host = os.environ.get("INTERDEC_SMTP_HOST", "").strip()
    user = os.environ.get("INTERDEC_SMTP_USER", "").strip()
    sender = os.environ.get("INTERDEC_SMTP_FROM", "").strip() or user
    try:
        port = int(os.environ.get("INTERDEC_SMTP_PORT", "587"))
    except ValueError:
        port = 587
    return {
        "host": host, "port": port, "user": user, "password": os.environ.get("INTERDEC_SMTP_PASSWORD", ""),
        "from": sender, "configured": bool(host and sender),
        "appUrl": os.environ.get("INTERDEC_APP_URL", "").rstrip("/"),
    }


def status() -> dict:
    c = config()
    return {"configured": c["configured"], "host": c["host"], "port": c["port"], "from": c["from"],
            "appUrl": c["appUrl"]}


def valid_email(addr: str) -> bool:
    name, a = parseaddr(addr or "")
    return bool(a) and "@" in a and "." in a.split("@")[-1] and " " not in a and len(a) <= 254


def _log(db, to, subject, kind, shipment_id, status_, error=""):
    db.add(models.EmailLog(id=uuid.uuid4().hex[:12], to=", ".join(to), subject=subject[:300], kind=kind,
                           shipment_id=shipment_id, status=status_, error=(error or "")[:500], ts=int(time.time() * 1000)))


def send(db, to: list[str], subject: str, html: str, text: str, kind: str = "", shipment_id: str | None = None) -> tuple[bool, str]:
    """Send one message to all recipients (BCC-style: each sees only themselves). Logs the outcome."""
    to = [a for a in dict.fromkeys(a.strip() for a in to) if valid_email(a)]
    if not to:
        return False, "No valid recipients"
    c = config()
    if not c["configured"]:
        _log(db, to, subject, kind, shipment_id, "not_configured", "Email is not set up (INTERDEC_SMTP_HOST)")
        return False, "Email isn't set up on the server yet"
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = c["from"] if "<" in c["from"] else formataddr(("Interdec ImportFlow", c["from"]))
    msg["To"] = to[0] if len(to) == 1 else "undisclosed-recipients:;"
    msg.set_content(text)
    msg.add_alternative(html, subtype="html")
    try:
        ctx = ssl.create_default_context()
        if c["port"] == 465:
            smtp = smtplib.SMTP_SSL(c["host"], c["port"], context=ctx, timeout=20)
        else:
            smtp = smtplib.SMTP(c["host"], c["port"], timeout=20)
            smtp.ehlo()
            if smtp.has_extn("starttls"):
                smtp.starttls(context=ctx)
                smtp.ehlo()
        with smtp:
            if c["user"]:
                smtp.login(c["user"], c["password"])
            smtp.send_message(msg, to_addrs=to)
    except Exception as e:  # network, auth, refused recipients…
        _log(db, to, subject, kind, shipment_id, "failed", f"{type(e).__name__}: {e}")
        return False, f"Sending failed: {e}"
    _log(db, to, subject, kind, shipment_id, "sent")
    return True, ""

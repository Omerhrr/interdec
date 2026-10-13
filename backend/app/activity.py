"""Activity log + notification helpers — shared by all routers."""
import time
import uuid

from . import models


def _ms() -> int:
    # time.time() is true UTC epoch; datetime.utcnow().timestamp() was shifted
    # by the server's local UTC offset (e.g. 1h off in Lagos).
    return int(time.time() * 1000)


def _id() -> str:
    return uuid.uuid4().hex[:12]


def log_action(db, user, action: str, detail: str, icon: str = "•"):
    """Record one activity feed entry (who did what)."""
    db.add(models.ActivityLog(
        id=_id(),
        user_id=getattr(user, "id", "") or "",
        user_name=getattr(user, "name", "") or "System",
        action=action,
        detail=detail,
        icon=icon,
        ts=_ms(),
    ))


def notify_users(db, db_users, message: str, kind: str = "info", icon: str = "🔔", exclude_user=None):
    """Push an in-app notification to the given users (skips the actor)."""
    for u in db_users:
        if exclude_user is not None and getattr(u, "id", "") == getattr(exclude_user, "id", ""):
            continue
        if not getattr(u, "active", True):
            continue
        db.add(models.Notification(
            id=_id(),
            user_id=u.id,
            message=message,
            kind=kind,
            icon=icon,
            ts=_ms(),
        ))

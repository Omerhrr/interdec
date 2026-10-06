"""Activity log + notification helpers — shared by all routers."""
from datetime import datetime
from . import models


def _ms() -> int:
    return int(datetime.utcnow().timestamp() * 1000)


def log_action(db, user, action: str, detail: str, icon: str = "•"):
    """Record one activity feed entry (who did what)."""
    entry = models.ActivityLog(
        id=datetime.utcnow().strftime("%f") + _rand(),
        user_id=getattr(user, "id", "") or "",
        user_name=getattr(user, "name", "") or "System",
        action=action,
        detail=detail,
        icon=icon,
        ts=_ms(),
    )
    db.add(entry)


def notify_users(db, db_users, message: str, kind: str = "info", icon: str = "🔔", exclude_user=None):
    """Push an in-app notification to the given users (skips the actor)."""
    for u in db_users:
        if exclude_user is not None and getattr(u, "id", "") == getattr(exclude_user, "id", ""):
            continue
        if not getattr(u, "active", True):
            continue
        db.add(models.Notification(
            id=datetime.utcnow().strftime("%f") + _rand(),
            user_id=u.id,
            message=message,
            kind=kind,
            icon=icon,
            ts=_ms(),
        ))


def _rand() -> str:
    import uuid
    return uuid.uuid4().hex[:6]

"""Activity feed + notifications endpoints."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from .. import models, auth

router = APIRouter(prefix="/api", tags=["activity"])


@router.get("/activity")
def recent_activity(limit: int = 30, db: Session = Depends(get_db),
                    user: models.User = Depends(auth.get_current_user)):
    rows = db.query(models.ActivityLog).order_by(models.ActivityLog.ts.desc()).limit(max(1, min(limit, 100))).all()
    return [
        {
            "id": r.id, "userId": r.user_id, "userName": r.user_name,
            "action": r.action, "detail": r.detail, "icon": r.icon, "ts": r.ts,
        }
        for r in rows
    ]


@router.get("/notifications")
def my_notifications(db: Session = Depends(get_db),
                     user: models.User = Depends(auth.get_current_user)):
    rows = (db.query(models.Notification)
            .filter(models.Notification.user_id == user.id)
            .order_by(models.Notification.ts.desc())
            .limit(50).all())
    return [
        {"id": n.id, "message": n.message, "kind": n.kind, "icon": n.icon,
         "read": n.read, "ts": n.ts}
        for n in rows
    ]


@router.get("/notifications/unread-count")
def unread_count(db: Session = Depends(get_db),
                 user: models.User = Depends(auth.get_current_user)):
    n = (db.query(models.Notification)
         .filter(models.Notification.user_id == user.id, models.Notification.read == False)  # noqa: E712
         .count())
    return {"count": n}


@router.post("/notifications/read-all")
def read_all(db: Session = Depends(get_db), user: models.User = Depends(auth.get_current_user)):
    db.query(models.Notification).filter(
        models.Notification.user_id == user.id, models.Notification.read == False  # noqa: E712
    ).update({"read": True})
    db.commit()
    return {"ok": True}


@router.post("/notifications/{nid}/read")
def read_one(nid: str, db: Session = Depends(get_db),
             user: models.User = Depends(auth.get_current_user)):
    n = db.query(models.Notification).filter(
        models.Notification.id == nid, models.Notification.user_id == user.id
    ).first()
    if not n:
        raise HTTPException(status_code=404, detail="Notification not found")
    n.read = True
    db.commit()
    return {"ok": True}

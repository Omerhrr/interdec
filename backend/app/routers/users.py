"""Users router — platform user management (admin)."""
import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from .. import models, auth
from ..schemas import UserOut, UserCreate, UserUpdate

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("", response_model=list[UserOut])
def list_users(user: models.User = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    users = db.query(models.User).order_by(models.User.created).all()
    return [UserOut.model_validate(u) for u in users]


DEFAULT_APPS = {
    "facade": {"access": False, "role": "sales"},
    "importflow": {"access": False, "role": "viewer"},
    "catalogues": {"access": False},
}


@router.post("", response_model=UserOut)
def create_user(
    body: UserCreate,
    admin: models.User = Depends(auth.require_admin),
    db: Session = Depends(get_db),
):
    email = body.email.strip().lower()
    if not email:
        raise HTTPException(400, "Email is required")
    if db.query(models.User).filter(models.User.email == email).first():
        raise HTTPException(400, "A user with this email already exists")
    if len(body.password) < 6:
        raise HTTPException(400, "Password must be at least 6 characters")
    apps = body.apps or {}
    merged = {k: {**v} for k, v in DEFAULT_APPS.items()}
    for k, v in apps.items():
        if k in merged:
            merged[k].update(v)
        else:
            merged[k] = v
    u = models.User(
        id=uuid.uuid4().hex[:12],
        name=body.name.strip(),
        email=email,
        password_hash=auth.hash_password(body.password),
        avatar=(body.avatar or body.name.strip()[:2]).upper()[:2],
        platform_role=body.platformRole if body.platformRole in ("admin", "user") else "user",
        apps=merged,
        active=True,
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return UserOut.model_validate(u)


@router.put("/{user_id}", response_model=UserOut)
def update_user(
    user_id: str,
    body: UserUpdate,
    admin: models.User = Depends(auth.require_admin),
    db: Session = Depends(get_db),
):
    u = db.query(models.User).filter(models.User.id == user_id).first()
    if not u:
        raise HTTPException(404, "User not found")
    if body.email is not None:
        new_email = body.email.strip().lower()
        existing = db.query(models.User).filter(models.User.email == new_email, models.User.id != user_id).first()
        if existing:
            raise HTTPException(400, "A user with this email already exists")
        u.email = new_email
    if body.name is not None:
        u.name = body.name.strip()
    if body.password:
        if len(body.password) < 6:
            raise HTTPException(400, "Password must be at least 6 characters")
        u.password_hash = auth.hash_password(body.password)
    if body.avatar is not None:
        u.avatar = body.avatar.upper()[:2]
    if body.platformRole is not None:
        if u.id == admin.id and body.platformRole != "admin":
            raise HTTPException(400, "You cannot remove your own admin role.")
        u.platform_role = body.platformRole if body.platformRole in ("admin", "user") else "user"
    if body.apps is not None:
        merged = dict(u.apps or {})
        for k, v in body.apps.items():
            if isinstance(v, dict):
                merged[k] = {**(merged.get(k) or {}), **v}
            else:
                merged[k] = v
        u.apps = merged
    if body.active is not None:
        if u.id == admin.id and not body.active:
            raise HTTPException(400, "You cannot disable your own account.")
        u.active = body.active
    db.commit()
    db.refresh(u)
    return UserOut.model_validate(u)


@router.delete("/{user_id}")
def delete_user(
    user_id: str,
    admin: models.User = Depends(auth.require_admin),
    db: Session = Depends(get_db),
):
    u = db.query(models.User).filter(models.User.id == user_id).first()
    if not u:
        raise HTTPException(404, "User not found")
    if u.id == admin.id:
        raise HTTPException(400, "You cannot delete your own account.")
    db.delete(u)
    db.commit()
    return {"ok": True}

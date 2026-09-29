"""Auth router — login/logout/me."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from .. import models, auth
from ..schemas import LoginRequest, TokenResponse, UserOut

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    email = body.email.strip().lower()
    user = db.query(models.User).filter(models.User.email == email).first()
    if not user or not auth.verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not user.active:
        raise HTTPException(status_code=403, detail="Account disabled. Contact your administrator.")
    token = auth.create_access_token(user.id, user.email)
    from ..activity import log_action
    log_action(db, user, "auth.login", f"{user.name} signed in", "🔓")
    db.commit()
    return TokenResponse(access_token=token, user=UserOut.model_validate(user))


@router.get("/me", response_model=UserOut)
def me(user: models.User = Depends(auth.get_current_user)):
    return UserOut.model_validate(user)


@router.post("/change-password")
def change_password(body: dict, db: Session = Depends(get_db),
                    user: models.User = Depends(auth.get_current_user)):
    current = (body.get("currentPassword") or "").strip()
    new = (body.get("newPassword") or "").strip()
    if not current or not new:
        raise HTTPException(status_code=400, detail="Current and new password are required")
    if len(new) < 6:
        raise HTTPException(status_code=400, detail="New password must be at least 6 characters")
    if not auth.verify_password(current, user.password_hash):
        raise HTTPException(status_code=401, detail="Current password is incorrect")
    if current == new:
        raise HTTPException(status_code=400, detail="New password must differ from the current one")
    user.password_hash = auth.hash_password(new)
    db.commit()
    from ..activity import log_action
    log_action(db, user, "auth.password_changed", f"{user.name} changed their password", "🔑")
    db.commit()
    return {"ok": True}

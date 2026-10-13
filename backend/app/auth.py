"""Auth utilities — JWT + password hashing + role guards."""
import os
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path

from jose import jwt, JWTError
from passlib.context import CryptContext
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from .database import get_db
from . import models


def _load_secret() -> str:
    """Signing key: INTERDEC_SECRET_KEY env var, else a random key persisted
    next to the database (so sessions survive restarts but the key is never a
    hard-coded, publicly known value)."""
    env = os.environ.get("INTERDEC_SECRET_KEY", "").strip()
    if env:
        return env
    key_file = Path(__file__).resolve().parent.parent / ".secret_key"
    try:
        if key_file.exists():
            k = key_file.read_text().strip()
            if len(k) >= 32:
                return k
        k = secrets.token_urlsafe(48)
        key_file.write_text(k)
        try:
            os.chmod(key_file, 0o600)
        except OSError:
            pass
        return k
    except OSError:
        # read-only filesystem: fall back to a per-process key
        return secrets.token_urlsafe(48)


SECRET_KEY = _load_secret()
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24 * 7  # 7 days

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return pwd_context.verify(plain, hashed)
    except (ValueError, TypeError):
        return False


def create_access_token(user_id: str, email: str) -> str:
    payload = {
        "sub": user_id,
        "email": email,
        "exp": datetime.now(timezone.utc) + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> models.User:
    if credentials is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid token")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")
    if not user.active:
        raise HTTPException(status_code=403, detail="Account disabled")
    return user


def require_admin(user: models.User = Depends(get_current_user)) -> models.User:
    if user.platform_role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


def importflow_role(user: models.User) -> str:
    """Resolve the user's ImportFlow role (platform admins are always admin)."""
    if user.platform_role == "admin":
        return "admin"
    apps = user.apps or {}
    flow = apps.get("importflow") or {}
    if not flow.get("access"):
        return "viewer"
    return flow.get("role") or "viewer"


def can_edit_importflow(user: models.User) -> bool:
    return importflow_role(user) in ("admin", "user")


def require_importflow_editor(user: models.User = Depends(get_current_user)) -> models.User:
    """Write access to ImportFlow data (projects, shipments, vendors, shippers)."""
    if not can_edit_importflow(user):
        raise HTTPException(status_code=403, detail="You have read-only access to ImportFlow")
    return user


def has_quotes_access(user: models.User) -> bool:
    """Quotations is the native replacement for the legacy facade app: platform
    admins and anyone with quotes or facade access may use it (matches the UI)."""
    if user.platform_role == "admin":
        return True
    apps = user.apps or {}
    return bool((apps.get("quotes") or {}).get("access") or (apps.get("facade") or {}).get("access"))


def is_quote_admin(user: models.User) -> bool:
    """Who may see costs and margins: platform admins and Quotations/Facade admins."""
    if user.platform_role == "admin":
        return True
    apps = user.apps or {}
    q, f = apps.get("quotes") or {}, apps.get("facade") or {}
    if q.get("access"):
        return q.get("role") == "admin"
    return bool(f.get("access")) and f.get("role") == "admin"


def require_quotes_access(user: models.User = Depends(get_current_user)) -> models.User:
    if not has_quotes_access(user):
        raise HTTPException(status_code=403, detail="You do not have access to Quotations")
    return user

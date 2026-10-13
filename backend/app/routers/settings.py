"""Platform settings — currency exchange rates used for USD totals.

Rates used to be hard-coded in the browser (and edits were lost on reload), so
every dashboard total was converted with numbers nobody could see or change.
They now live on the server with the date and person of the last change.
"""
import time

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from .. import models, auth
from ..activity import log_action

router = APIRouter(prefix="/api/settings", tags=["settings"])

FX_KEY = "fxRates"
DEFAULT_FX = {"USD": 1, "EUR": 1.08, "GBP": 1.27, "JPY": 0.0067, "CNY": 0.14, "ILS": 0.27, "AED": 0.27, "NGN": 0.00065}


class FxUpdate(BaseModel):
    rates: dict


def _row(db: Session):
    return db.query(models.FacadeSetting).filter(models.FacadeSetting.key == FX_KEY).first()


def _out(row) -> dict:
    v = (row.value if row else None) or {}
    return {
        "rates": {**DEFAULT_FX, **(v.get("rates") or {})},
        "updated": row.updated if row else 0,
        "updatedBy": v.get("updatedBy", ""),
        "isDefault": row is None,
    }


@router.get("/fx")
def get_fx(user: models.User = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    return _out(_row(db))


@router.put("/fx")
def put_fx(body: FxUpdate, user: models.User = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    if auth.importflow_role(user) != "admin":
        raise HTTPException(403, "Only ImportFlow admins can change exchange rates")
    clean = {}
    for code, val in (body.rates or {}).items():
        code = str(code).upper().strip()
        if not code.isalpha() or len(code) != 3:
            raise HTTPException(400, f"Invalid currency code: {code}")
        try:
            f = float(val)
        except (TypeError, ValueError):
            raise HTTPException(400, f"{code} rate must be a number")
        if not (f > 0) or f > 1e6:
            raise HTTPException(400, f"{code} rate must be greater than zero")
        clean[code] = f
    clean["USD"] = 1.0
    row = _row(db)
    value = {"rates": clean, "updatedBy": user.name}
    now = int(time.time() * 1000)
    if row:
        row.value = value
        row.updated = now
    else:
        row = models.FacadeSetting(key=FX_KEY, value=value, updated=now)
        db.add(row)
    log_action(db, user, "settings.fx", "Updated exchange rates", "💱")
    db.commit()
    return _out(row)

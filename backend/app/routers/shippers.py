"""Shippers router — CRUD."""
import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from .. import models, auth
from ..schemas import ShipperCreate, ShipperUpdate

router = APIRouter(prefix="/api/shippers", tags=["shippers"])


def _out(s: models.Shipper) -> dict:
    return {
        "id": s.id,
        "name": s.name,
        "contact": s.contact,
        "email": s.email,
        "phone": s.phone,
        "country": s.country,
        "category": s.category,
        "notes": s.notes,
        "created": s.created,
    }


@router.get("")
def list_shippers(
    user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    return [_out(s) for s in db.query(models.Shipper).order_by(models.Shipper.created.desc()).all()]


@router.post("")
def create_shipper(
    body: ShipperCreate,
    user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    import time
    s = models.Shipper(id=uuid.uuid4().hex[:12], **body.model_dump(), created=int(time.time() * 1000))
    db.add(s)
    db.commit()
    db.refresh(s)
    return _out(s)


@router.put("/{shipper_id}")
def update_shipper(
    shipper_id: str,
    body: ShipperUpdate,
    user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    s = db.query(models.Shipper).filter(models.Shipper.id == shipper_id).first()
    if not s:
        raise HTTPException(404, "Shipper not found")
    for k, val in body.model_dump(exclude_none=True).items():
        setattr(s, k, val)
    db.commit()
    db.refresh(s)
    return _out(s)


@router.delete("/{shipper_id}")
def delete_shipper(
    shipper_id: str,
    user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    s = db.query(models.Shipper).filter(models.Shipper.id == shipper_id).first()
    if not s:
        raise HTTPException(404, "Shipper not found")
    db.query(models.Shipment).filter(models.Shipment.shipper_id == shipper_id).update({"shipper_id": None})
    db.delete(s)
    db.commit()
    return {"ok": True}

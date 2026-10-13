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
    user: models.User = Depends(auth.require_importflow_editor),
    db: Session = Depends(get_db),
):
    import time
    data = body.model_dump()
    data["name"] = data["name"].strip()
    if not data["name"]:
        raise HTTPException(400, "Company name is required")
    s = models.Shipper(id=uuid.uuid4().hex[:12], **data, created=int(time.time() * 1000))
    db.add(s)
    from ..activity import log_action
    log_action(db, user, "shipper.created", f"Created shipper {s.name}", "🚢")
    db.commit()
    db.refresh(s)
    return _out(s)


@router.put("/{shipper_id}")
def update_shipper(
    shipper_id: str,
    body: ShipperUpdate,
    user: models.User = Depends(auth.require_importflow_editor),
    db: Session = Depends(get_db),
):
    s = db.query(models.Shipper).filter(models.Shipper.id == shipper_id).first()
    if not s:
        raise HTTPException(404, "Shipper not found")
    data = body.model_dump(exclude_none=True)
    if "name" in data:
        data["name"] = data["name"].strip()
        if not data["name"]:
            raise HTTPException(400, "Company name is required")
    for k, val in data.items():
        setattr(s, k, val)
    from ..activity import log_action
    log_action(db, user, "shipper.updated", f"Updated shipper {s.name}", "✏️")
    db.commit()
    db.refresh(s)
    return _out(s)


@router.delete("/{shipper_id}")
def delete_shipper(
    shipper_id: str,
    user: models.User = Depends(auth.require_importflow_editor),
    db: Session = Depends(get_db),
):
    s = db.query(models.Shipper).filter(models.Shipper.id == shipper_id).first()
    if not s:
        raise HTTPException(404, "Shipper not found")
    in_use = db.query(models.Shipment).filter(models.Shipment.shipper_id == shipper_id).count()
    if in_use:
        # detaching would leave shipped/completed cycles without a carrier
        raise HTTPException(400, f"Shipper is assigned to {in_use} shipment(s); reassign those first")
    name = s.name
    db.delete(s)
    from ..activity import log_action
    log_action(db, user, "shipper.deleted", f"Deleted shipper {name}", "🗑")
    db.commit()
    return {"ok": True}

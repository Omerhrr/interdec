"""Clearing agents router — CRUD (same shape as shippers)."""
import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from .. import models, auth
from ..schemas import ShipperCreate as AgentCreate, ShipperUpdate as AgentUpdate

router = APIRouter(prefix="/api/clearing-agents", tags=["clearing-agents"])


def _out(s: models.ClearingAgent) -> dict:
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
def list_agents(
    user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    return [_out(s) for s in db.query(models.ClearingAgent).order_by(models.ClearingAgent.created.desc()).all()]


@router.post("")
def create_agent(
    body: AgentCreate,
    user: models.User = Depends(auth.require_importflow_editor),
    db: Session = Depends(get_db),
):
    import time
    data = body.model_dump()
    data["name"] = data["name"].strip()
    if not data["name"]:
        raise HTTPException(400, "Company name is required")
    s = models.ClearingAgent(id=uuid.uuid4().hex[:12], **data, created=int(time.time() * 1000))
    db.add(s)
    from ..activity import log_action
    log_action(db, user, "clearing_agent.created", f"Created clearing agent {s.name}", "🚢")
    db.commit()
    db.refresh(s)
    return _out(s)


@router.put("/{agent_id}")
def update_agent(
    agent_id: str,
    body: AgentUpdate,
    user: models.User = Depends(auth.require_importflow_editor),
    db: Session = Depends(get_db),
):
    s = db.query(models.ClearingAgent).filter(models.ClearingAgent.id == agent_id).first()
    if not s:
        raise HTTPException(404, "Clearing agent not found")
    data = body.model_dump(exclude_none=True)
    if "name" in data:
        data["name"] = data["name"].strip()
        if not data["name"]:
            raise HTTPException(400, "Company name is required")
    for k, val in data.items():
        setattr(s, k, val)
    from ..activity import log_action
    log_action(db, user, "clearing_agent.updated", f"Updated clearing agent {s.name}", "✏️")
    db.commit()
    db.refresh(s)
    return _out(s)


@router.delete("/{agent_id}")
def delete_agent(
    agent_id: str,
    user: models.User = Depends(auth.require_importflow_editor),
    db: Session = Depends(get_db),
):
    s = db.query(models.ClearingAgent).filter(models.ClearingAgent.id == agent_id).first()
    if not s:
        raise HTTPException(404, "Clearing agent not found")
    in_use = db.query(models.Shipment).filter(models.Shipment.clearing_agent_id == agent_id).count()
    if in_use:
        # detaching would leave cleared shipments without their agent
        raise HTTPException(400, f"This agent is clearing {in_use} shipment(s); reassign those first")
    name = s.name
    db.delete(s)
    from ..activity import log_action
    log_action(db, user, "clearing_agent.deleted", f"Deleted clearing agent {name}", "🗑")
    db.commit()
    return {"ok": True}

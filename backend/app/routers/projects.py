"""Projects router — CRUD."""
import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from .. import models, auth, finance
from ..schemas import ProjectCreate, ProjectUpdate

router = APIRouter(prefix="/api/projects", tags=["projects"])


def _out(p: models.Project) -> dict:
    return {
        "id": p.id,
        "name": p.name,
        "client": p.client,
        "description": p.description,
        "status": p.status,
        "created": p.created,
    }


@router.get("/budgets")
def project_budgets(user: models.User = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    """Budget vs actual for every project (naira): contract value from won quotes vs landed cost of its shipments."""
    money = finance.Money(db)
    return {p.id: finance.project_budget(db, p, money) for p in db.query(models.Project).all()}


@router.get("/{project_id}/budget")
def project_budget(project_id: str, user: models.User = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    p = db.query(models.Project).filter(models.Project.id == project_id).first()
    if not p:
        raise HTTPException(404, "Project not found")
    return finance.project_budget(db, p)


@router.get("")
def list_projects(user: models.User = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    return [_out(p) for p in db.query(models.Project).order_by(models.Project.created.desc()).all()]


@router.post("")
def create_project(
    body: ProjectCreate,
    user: models.User = Depends(auth.require_importflow_editor),
    db: Session = Depends(get_db),
):
    import time
    data = body.model_dump()
    data["name"] = data["name"].strip()
    if not data["name"]:
        raise HTTPException(400, "Project name is required")
    p = models.Project(id=uuid.uuid4().hex[:12], **data, created=int(time.time() * 1000))
    db.add(p)
    from ..activity import log_action
    log_action(db, user, "project.created", f"Created project {p.name}", "📋")
    db.commit()
    db.refresh(p)
    return _out(p)


@router.put("/{project_id}")
def update_project(
    project_id: str,
    body: ProjectUpdate,
    user: models.User = Depends(auth.require_importflow_editor),
    db: Session = Depends(get_db),
):
    p = db.query(models.Project).filter(models.Project.id == project_id).first()
    if not p:
        raise HTTPException(404, "Project not found")
    data = body.model_dump(exclude_none=True)
    if "name" in data:
        data["name"] = data["name"].strip()
        if not data["name"]:
            raise HTTPException(400, "Project name is required")
    for k, val in data.items():
        setattr(p, k, val)
    # keep the project-name snapshot on linked quotes in sync
    if "name" in data:
        db.query(models.Quote).filter(models.Quote.project_id == project_id).update({"project_name": p.name})
    from ..activity import log_action
    log_action(db, user, "project.updated", f"Updated project {p.name}", "✏️")
    db.commit()
    db.refresh(p)
    return _out(p)


@router.delete("/{project_id}")
def delete_project(
    project_id: str,
    user: models.User = Depends(auth.require_importflow_editor),
    db: Session = Depends(get_db),
):
    p = db.query(models.Project).filter(models.Project.id == project_id).first()
    if not p:
        raise HTTPException(404, "Project not found")
    db.query(models.Shipment).filter(models.Shipment.project_id == project_id).update({"project_id": None})
    db.query(models.Quote).filter(models.Quote.project_id == project_id).update({"project_id": None})
    db.delete(p)
    from ..activity import log_action
    log_action(db, user, "project.deleted", f"Deleted project {p.name}", "🗑")
    db.commit()
    return {"ok": True}

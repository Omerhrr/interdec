"""Vendors router — CRUD + PDF catalogue upload/download.

Hardened: write access needs an ImportFlow editor role, uploads are validated
(base64, size, count), filenames are sanitised and only safe types are served
inline, and vendors still used by shipments cannot be deleted.
"""
import time
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from .. import models, auth
from ..activity import log_action, notify_users
from ..files import validate_upload, file_response
from ..schemas import VendorCreate, VendorUpdate, CatalogFile

router = APIRouter(prefix="/api/vendors", tags=["vendors"])

MAX_CATALOGS_PER_VENDOR = 50


def _cat_meta(c: dict) -> dict:
    return {k: c.get(k) for k in ("name", "size", "type", "uploaded")}


def _out(v: models.Vendor) -> dict:
    return {
        "id": v.id,
        "name": v.name,
        "contact": v.contact,
        "email": v.email,
        "phone": v.phone,
        "country": v.country,
        "category": v.category,
        "address": v.address,
        "notes": v.notes,
        "catalogs": [_cat_meta(c) for c in (v.catalogs or []) if isinstance(c, dict)],
        "created": v.created,
    }


def _get(db: Session, vendor_id: str) -> models.Vendor:
    v = db.query(models.Vendor).filter(models.Vendor.id == vendor_id).first()
    if not v:
        raise HTTPException(404, "Vendor not found")
    return v


@router.get("")
def list_vendors(
    category: Optional[str] = None,
    user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    q = db.query(models.Vendor).order_by(models.Vendor.created.desc())
    if category and category != "All":
        q = q.filter(models.Vendor.category == category)
    return [_out(v) for v in q.all()]


@router.post("")
def create_vendor(
    body: VendorCreate,
    user: models.User = Depends(auth.require_importflow_editor),
    db: Session = Depends(get_db),
):
    data = body.model_dump()
    data["name"] = (data.get("name") or "").strip()
    if not data["name"]:
        raise HTTPException(400, "Company name is required")
    v = models.Vendor(id=uuid.uuid4().hex[:12], **data, catalogs=[], created=int(time.time() * 1000))
    db.add(v)
    log_action(db, user, "vendor.created", f"Created vendor {v.name}", "🏗")
    db.commit()
    db.refresh(v)
    return _out(v)


@router.put("/{vendor_id}")
def update_vendor(
    vendor_id: str,
    body: VendorUpdate,
    user: models.User = Depends(auth.require_importflow_editor),
    db: Session = Depends(get_db),
):
    v = _get(db, vendor_id)
    data = body.model_dump(exclude_none=True)
    if "name" in data:
        data["name"] = data["name"].strip()
        if not data["name"]:
            raise HTTPException(400, "Company name is required")
    for k, val in data.items():
        setattr(v, k, val)
    log_action(db, user, "vendor.updated", f"Updated vendor {v.name}", "✏️")
    db.commit()
    db.refresh(v)
    return _out(v)


@router.delete("/{vendor_id}")
def delete_vendor(
    vendor_id: str,
    user: models.User = Depends(auth.require_importflow_editor),
    db: Session = Depends(get_db),
):
    v = _get(db, vendor_id)
    in_use = db.query(models.Shipment).filter(models.Shipment.vendor_id == vendor_id).count()
    if in_use:
        raise HTTPException(400, f"Vendor is used by {in_use} shipment(s); reassign or delete those first")
    name = v.name
    db.delete(v)
    log_action(db, user, "vendor.deleted", f"Deleted vendor {name}", "🗑")
    db.commit()
    return {"ok": True}


# ---------------------------------------------------------------------------
# Catalogues
# ---------------------------------------------------------------------------

@router.get("/{vendor_id}/catalogs")
def list_catalogs(vendor_id: str, user: models.User = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    return _out(_get(db, vendor_id))["catalogs"]


@router.post("/{vendor_id}/catalogs")
def upload_catalogs(
    vendor_id: str,
    body: list[CatalogFile],
    user: models.User = Depends(auth.require_catalogue_manager),
    db: Session = Depends(get_db),
):
    v = _get(db, vendor_id)
    if not body:
        raise HTTPException(400, "No files uploaded")
    existing = list(v.catalogs or [])
    if len(existing) + len(body) > MAX_CATALOGS_PER_VENDOR:
        raise HTTPException(400, f"A vendor can hold at most {MAX_CATALOGS_PER_VENDOR} catalogues")
    now = int(time.time() * 1000)
    for f in body:
        clean = validate_upload(f.model_dump(), "Catalogue")
        clean["uploaded"] = clean["uploaded"] or now
        existing.append(clean)
    v.catalogs = existing  # reassign so SQLAlchemy persists the JSON change
    log_action(db, user, "vendor.catalog_uploaded", f"Uploaded {len(body)} catalogue PDF(s) to {v.name}", "📄")
    notify_users(db, db.query(models.User).filter(models.User.active == True).all(),  # noqa: E712
                 f"New catalogue uploaded: {v.name} ({len(body)} file(s))", "success", "📄", exclude_user=user)
    db.commit()
    db.refresh(v)
    return _out(v)["catalogs"]


@router.delete("/{vendor_id}/catalogs/{index}")
def delete_catalog(
    vendor_id: str,
    index: int,
    user: models.User = Depends(auth.require_catalogue_manager),
    db: Session = Depends(get_db),
):
    v = _get(db, vendor_id)
    cats = list(v.catalogs or [])
    if index < 0 or index >= len(cats):
        raise HTTPException(404, "Catalogue not found")
    removed = cats.pop(index)
    v.catalogs = cats
    log_action(db, user, "vendor.catalog_removed", f"Removed catalogue {removed.get('name', '')} from {v.name}", "🗑")
    db.commit()
    return {"ok": True}


@router.get("/{vendor_id}/catalogs/{index}/download")
def download_catalog(
    vendor_id: str,
    index: int,
    user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    v = _get(db, vendor_id)
    cats = v.catalogs or []
    if index < 0 or index >= len(cats):
        raise HTTPException(404, "Catalogue not found")
    return file_response(cats[index], "catalog.pdf")

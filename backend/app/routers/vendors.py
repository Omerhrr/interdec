"""Vendors router — CRUD + catalog upload/download."""
import base64
import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from .. import models, auth
from ..schemas import VendorCreate, VendorUpdate, CatalogFile

router = APIRouter(prefix="/api/vendors", tags=["vendors"])


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
        # catalogs listed without heavy base64 payload
        "catalogs": [
            {"name": c.get("name"), "size": c.get("size", 0), "type": c.get("type", ""), "uploaded": c.get("uploaded", 0)}
            for c in (v.catalogs or [])
        ],
        "created": v.created,
    }


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


@router.get("/{vendor_id}/catalogs")
def list_catalogs(
    vendor_id: str,
    user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    v = db.query(models.Vendor).filter(models.Vendor.id == vendor_id).first()
    if not v:
        raise HTTPException(404, "Vendor not found")
    return _out(v)["catalogs"]


@router.get("/{vendor_id}/catalogs/{index}/download")
def download_catalog(
    vendor_id: str,
    index: int,
    user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    v = db.query(models.Vendor).filter(models.Vendor.id == vendor_id).first()
    if not v:
        raise HTTPException(404, "Vendor not found")
    catalogs = v.catalogs or []
    if index < 0 or index >= len(catalogs):
        raise HTTPException(404, "Catalog not found")
    c = catalogs[index]
    data = c.get("data") or ""
    try:
        raw = base64.b64decode(data)
    except Exception:
        raise HTTPException(500, "Corrupted file data")
    from fastapi.responses import Response
    media = c.get("type") or "application/pdf"
    if not media.startswith("application/") and not media.startswith("image/"):
        media = "application/octet-stream"
    return Response(
        content=raw,
        media_type=media,
        headers={"Content-Disposition": f'inline; filename="{c.get("name", "catalog.pdf")}"'},
    )


@router.post("/{vendor_id}/catalogs")
def upload_catalog(
    vendor_id: str,
    files: list[CatalogFile],
    user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    v = db.query(models.Vendor).filter(models.Vendor.id == vendor_id).first()
    if not v:
        raise HTTPException(404, "Vendor not found")
    catalogs = list(v.catalogs or [])
    for f in files:
        catalogs.append(f.model_dump())
    v.catalogs = catalogs
    from ..activity import log_action, notify_users
    log_action(db, user, "vendor.catalog_uploaded", f"Uploaded {len(files)} catalogue PDF(s) to {v.name}", "📄")
    notify_users(db, db.query(models.User).filter(models.User.active == True).all(),  # noqa: E712
                 f"New catalogue uploaded: {v.name} ({len(files)} file(s))", "success", "📄", exclude_user=user)
    db.commit()
    return _out(v)["catalogs"]


@router.delete("/{vendor_id}/catalogs/{index}")
def delete_catalog(
    vendor_id: str,
    index: int,
    user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    v = db.query(models.Vendor).filter(models.Vendor.id == vendor_id).first()
    if not v:
        raise HTTPException(404, "Vendor not found")
    catalogs = list(v.catalogs or [])
    if index < 0 or index >= len(catalogs):
        raise HTTPException(404, "Catalog not found")
    catalogs.pop(index)
    v.catalogs = catalogs
    db.commit()
    return {"ok": True}


@router.post("")
def create_vendor(
    body: VendorCreate,
    user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    import time
    v = models.Vendor(
        id=uuid.uuid4().hex[:12],
        **body.model_dump(),
        catalogs=[],
        created=int(time.time() * 1000),
    )
    db.add(v)
    from ..activity import log_action
    log_action(db, user, "vendor.created", f"Created vendor {v.name}", "🏗")
    db.commit()
    db.refresh(v)
    return _out(v)


@router.put("/{vendor_id}")
def update_vendor(
    vendor_id: str,
    body: VendorUpdate,
    user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    v = db.query(models.Vendor).filter(models.Vendor.id == vendor_id).first()
    if not v:
        raise HTTPException(404, "Vendor not found")
    for k, val in body.model_dump(exclude_none=True).items():
        setattr(v, k, val)
    from ..activity import log_action
    log_action(db, user, "vendor.updated", f"Updated vendor {v.name}", "✏️")
    db.commit()
    db.refresh(v)
    return _out(v)


@router.delete("/{vendor_id}")
def delete_vendor(
    vendor_id: str,
    user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    v = db.query(models.Vendor).filter(models.Vendor.id == vendor_id).first()
    if not v:
        raise HTTPException(404, "Vendor not found")
    # detach from shipments
    db.query(models.Shipment).filter(models.Shipment.vendor_id == vendor_id).update({"vendor_id": None})
    db.delete(v)
    from ..activity import log_action
    log_action(db, user, "vendor.deleted", f"Deleted vendor {v.name}", "🗑")
    db.commit()
    return {"ok": True}

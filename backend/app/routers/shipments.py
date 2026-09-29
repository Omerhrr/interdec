"""Shipments router — CRUD + workflow transitions + document uploads."""
import base64
import time
import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from .. import models, auth
from ..schemas import ShipmentCreate, ShipmentUpdate

router = APIRouter(prefix="/api/shipments", tags=["shipments"])


def _file_meta(f):
    """File metadata without base64 payload."""
    if not f:
        return None
    if isinstance(f, dict):
        return {k: f.get(k) for k in ("name", "size", "type", "uploaded")}
    return None


def _out(s: models.Shipment) -> dict:
    return {
        "id": s.id,
        "ref": s.ref,
        "companyId": s.company_id,
        "projectId": s.project_id,
        "category": s.category,
        "vendorId": s.vendor_id,
        "shipperId": s.shipper_id,
        "status": s.status,
        "paymentTerms": s.payment_terms,
        "eta": s.eta,
        "shipMethod": s.ship_method,
        "description": s.description,
        "productionDays": s.production_days,
        "value": s.value,
        "currency": s.currency,
        "vendorInvoice": _file_meta(s.vendor_invoice),
        "packingList": _file_meta(s.packing_list),
        "shipperInvoice": _file_meta(s.shipper_invoice),
        "goodsConfirmed": s.goods_confirmed,
        "dates": s.dates or {},
        "created": s.created,
        "updated": s.updated,
    }


def _next_ref(db: Session) -> str:
    count = db.query(models.Shipment).count()
    return f"IMP-2026-{count + 1:03d}"


@router.get("")
def list_shipments(
    company: Optional[str] = None,
    status: Optional[str] = None,
    user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    q = db.query(models.Shipment).order_by(models.Shipment.created.desc())
    if company and company != "All":
        q = q.filter(models.Shipment.company_id == company)
    if status and status != "All":
        q = q.filter(models.Shipment.status == status)
    return [_out(s) for s in q.all()]


@router.post("")
def create_shipment(
    body: ShipmentCreate,
    user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    if not body.companyId:
        raise HTTPException(400, "Company is required")
    if not body.category:
        raise HTTPException(400, "Category is required")
    if not body.vendorId:
        raise HTTPException(400, "Vendor is required")
    if not body.description or not body.description.strip():
        raise HTTPException(400, "Description is required")
    now = int(time.time() * 1000)
    s = models.Shipment(
        id=uuid.uuid4().hex[:12],
        ref=_next_ref(db),
        company_id=body.companyId,
        project_id=body.projectId or None,
        category=body.category,
        vendor_id=body.vendorId,
        shipper_id=None,
        status="order_placed",
        payment_terms=None,
        eta="",
        ship_method="",
        description=body.description.strip(),
        production_days=body.productionDays or "",
        value=float(body.value or 0),
        currency=body.currency or "USD",
        vendor_invoice=None,
        packing_list=None,
        shipper_invoice=None,
        goods_confirmed=False,
        dates={"created": now},
        created=now,
        updated=now,
    )
    db.add(s)
    db.commit()
    db.refresh(s)
    return _out(s)


@router.get("/{shipment_id}/files/{kind}")
def download_file(
    shipment_id: str,
    kind: str,
    user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    s = db.query(models.Shipment).filter(models.Shipment.id == shipment_id).first()
    if not s:
        raise HTTPException(404, "Shipment not found")
    field = {"vendorInvoice": s.vendor_invoice, "packingList": s.packing_list, "shipperInvoice": s.shipper_invoice}.get(kind)
    if not field:
        raise HTTPException(404, "File not uploaded")
    try:
        raw = base64.b64decode(field.get("data") or "")
    except Exception:
        raise HTTPException(500, "Corrupted file data")
    from fastapi.responses import Response
    media = field.get("type") or "application/pdf"
    if not (media.startswith("application/") or media.startswith("image/") or media.startswith("text/")):
        media = "application/octet-stream"
    return Response(content=raw, media_type=media,
                    headers={"Content-Disposition": f'inline; filename="{field.get("name", "document.pdf")}"'})


@router.put("/{shipment_id}")
def update_shipment(
    shipment_id: str,
    body: ShipmentUpdate,
    user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    s = db.query(models.Shipment).filter(models.Shipment.id == shipment_id).first()
    if not s:
        raise HTTPException(404, "Shipment not found")
    role = auth.importflow_role(user)
    can_edit = role in ("admin", "user")
    now = int(time.time() * 1000)
    dates = dict(s.dates or {})
    data = body.model_dump(exclude_none=True)

    if "productionDays" in data:
        s.production_days = data["productionDays"]

    # Document uploads drive workflow status (only admin/user can edit)
    if "vendorInvoice" in data:
        if not can_edit:
            raise HTTPException(403, "Not allowed")
        f = data["vendorInvoice"]
        s.vendor_invoice = f
        dates["invoiceUploaded"] = now
        if s.status == "order_placed":
            s.status = "under_production"
    if "packingList" in data:
        if not can_edit:
            raise HTTPException(403, "Not allowed")
        s.packing_list = data["packingList"]
        dates["packingReady"] = now
    if "shipperInvoice" in data:
        if not can_edit:
            raise HTTPException(403, "Not allowed")
        s.shipper_invoice = data["shipperInvoice"]
        dates["shipperInvoiced"] = now
    if "goodsConfirmed" in data:
        if not can_edit:
            raise HTTPException(403, "Not allowed")
        s.goods_confirmed = bool(data["goodsConfirmed"])
        if data["goodsConfirmed"] and s.status == "in_transit":
            s.status = "completed"
            dates["closed"] = now
    if "shipperId" in data:
        if not can_edit:
            raise HTTPException(403, "Not allowed")
        s.shipper_id = data["shipperId"] or None
        if s.shipper_id:
            dates["shipperSelected"] = now
            # Ship goods: requires packing list + shipper -> moves to in_transit
            if s.packing_list and s.status == "under_production":
                s.status = "in_transit"
                dates["shipped"] = now
    if "paymentTerms" in data:
        if not can_edit:
            raise HTTPException(403, "Not allowed")
        s.payment_terms = data["paymentTerms"]
    if "eta" in data:
        if not can_edit:
            raise HTTPException(403, "Not allowed")
        s.eta = data["eta"]
    if "shipMethod" in data:
        if not can_edit:
            raise HTTPException(403, "Not allowed")
        s.ship_method = data["shipMethod"]
    if "status" in data and can_edit:
        # manual status override (admin)
        s.status = data["status"]

    s.dates = dates
    s.updated = now
    db.commit()
    db.refresh(s)
    return _out(s)


@router.delete("/{shipment_id}")
def delete_shipment(
    shipment_id: str,
    user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    s = db.query(models.Shipment).filter(models.Shipment.id == shipment_id).first()
    if not s:
        raise HTTPException(404, "Shipment not found")
    db.delete(s)
    db.commit()
    return {"ok": True}

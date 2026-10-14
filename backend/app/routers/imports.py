"""Import from Excel/CSV: template download, preview with per-row errors, commit."""
import io
import time

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ..database import get_db
from .. import models, auth, importer
from ..activity import log_action
from ..files import content_disposition

router = APIRouter(prefix="/api/import", tags=["import"])


def _check(kind: str, user: models.User):
    if kind not in importer.KINDS:
        raise HTTPException(404, f"Unknown import. Valid: {sorted(importer.KINDS)}")
    if importer.KINDS[kind]["who"] == "admin":
        if user.platform_role != "admin":
            raise HTTPException(403, "Only platform admins can import price lists")
    elif not auth.can_edit_importflow(user):
        raise HTTPException(403, "You have read-only access to ImportFlow")


def _ctx(db):
    from .quotes import get_catalog
    from .. import finance
    return importer.Ctx(db, get_catalog(db), list(finance.fx_rates(db)))


def _analyse(kind, body, db):
    try:
        rows = importer.read_rows((body or {}).get("file"))
        ctx = _ctx(db)
        return ctx, importer.analyse(kind, rows, ctx)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.get("/{kind}/template")
def template(kind: str, user: models.User = Depends(auth.get_current_user)):
    _check(kind, user)
    data = importer.template(kind)
    name = f"interdec-{kind}-template.xlsx"
    return StreamingResponse(io.BytesIO(data), media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                             headers={"Content-Disposition": content_disposition("attachment", name)})


@router.post("/{kind}/preview")
def preview(kind: str, body: dict, user: models.User = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    _check(kind, user)
    _, rows = _analyse(kind, body, db)
    return {"kind": kind, "title": importer.KINDS[kind]["title"],
            "columns": [c[1] for c in importer.KINDS[kind]["cols"]],
            "rows": [{k: v for k, v in r.items() if k != "clean"} for r in rows],
            "summary": {"total": len(rows), "create": sum(1 for r in rows if not r["errors"] and r["action"] == "create"),
                        "update": sum(1 for r in rows if not r["errors"] and r["action"] == "update"),
                        "errors": sum(1 for r in rows if r["errors"])}}


@router.post("/{kind}/commit")
def commit(kind: str, body: dict, user: models.User = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    _check(kind, user)
    ctx, rows = _analyse(kind, body, db)
    if not any(not r["errors"] for r in rows):
        raise HTTPException(400, "No valid rows to import. Fix the errors shown in the preview and upload again.")
    title = importer.KINDS[kind]["title"]
    if kind in ("glass", "acp", "hardware"):
        key, value, cur, done = importer.apply_prices(kind, rows, ctx.catalog, user)
        now = int(time.time() * 1000)
        for k, v in ((key, value), ("currencies", cur)):
            row = db.query(models.FacadeSetting).filter(models.FacadeSetting.key == k).first()
            if row:
                row.value, row.updated = v, now
            else:
                db.add(models.FacadeSetting(key=k, value=v, updated=now))
    else:
        done = importer.apply(kind, rows, ctx, user)
    log_action(db, user, "import", f"Imported {title.lower()}: {done['created']} added, {done['updated']} updated"
               + (f", {done['skipped']} skipped" if done["skipped"] else ""), "📥")
    db.commit()
    return done

"""Shared helpers for base64 file uploads/downloads (shipment docs, vendor catalogues)."""
import base64
import binascii
import re
import urllib.parse

from fastapi import HTTPException
from fastapi.responses import Response

MAX_FILE_BYTES = 15 * 1024 * 1024  # 15 MB per document

# Types that are safe to render inline in the browser. Anything else (notably
# text/html, image/svg+xml, application/xhtml+xml) is forced to download so an
# uploaded file can never run script on the application's origin.
_INLINE_SAFE = {
    "application/pdf", "image/png", "image/jpeg", "image/gif", "image/webp", "text/plain",
}


def safe_filename(name: str, default: str = "document") -> str:
    name = (name or "").replace("\\", "/").split("/")[-1]
    name = re.sub(r"[\x00-\x1f\x7f\"<>|:*?]", "_", name).strip(" .")
    return name[:180] or default


def validate_upload(f: dict, label: str = "File") -> dict:
    """Normalise an uploaded {name,size,type,data,uploaded} dict, checking the
    base64 payload decodes and fits the size limit."""
    if not isinstance(f, dict):
        raise HTTPException(400, f"{label}: invalid file payload")
    data = f.get("data") or ""
    if len(data) > MAX_FILE_BYTES * 4 // 3 + 16:
        raise HTTPException(413, f"{label} is too large (max {MAX_FILE_BYTES // (1024 * 1024)} MB)")
    try:
        raw = base64.b64decode(data, validate=True) if data else b""
    except (binascii.Error, ValueError):
        raise HTTPException(400, f"{label}: file data is not valid base64")
    if len(raw) > MAX_FILE_BYTES:
        raise HTTPException(413, f"{label} is too large (max {MAX_FILE_BYTES // (1024 * 1024)} MB)")
    return {
        "name": safe_filename(str(f.get("name") or "")),
        "size": len(raw),
        "type": str(f.get("type") or "application/octet-stream")[:100],
        "data": data,
        "uploaded": int(f.get("uploaded") or 0),
    }


def content_disposition(disposition: str, filename: str) -> str:
    fn = safe_filename(filename)
    ascii_fn = fn.encode("ascii", "replace").decode("ascii").replace("?", "_")
    return f'{disposition}; filename="{ascii_fn}"; filename*=UTF-8\'\'{urllib.parse.quote(fn)}'


def file_response(f: dict, default_name: str = "document") -> Response:
    try:
        raw = base64.b64decode(f.get("data") or "")
    except (binascii.Error, ValueError):
        raise HTTPException(500, "Corrupted file data")
    if not raw:
        raise HTTPException(404, "This file has no stored content (demo record)")
    media = (f.get("type") or "application/octet-stream").split(";")[0].strip().lower()
    inline = media in _INLINE_SAFE
    if not inline:
        media = "application/octet-stream"
    return Response(
        content=raw,
        media_type=media,
        headers={
            "Content-Disposition": content_disposition("inline" if inline else "attachment", f.get("name") or default_name),
            "X-Content-Type-Options": "nosniff",
        },
    )

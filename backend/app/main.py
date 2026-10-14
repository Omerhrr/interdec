"""Interdec Platform — FastAPI backend entrypoint."""
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .database import Base, engine, SessionLocal
from . import eta_alerts
from .seed import seed
from .routers import auth_router, users, vendors, shippers, projects, shipments, activity, quotes, settings, exports, clearing_agents, imports

Base.metadata.create_all(bind=engine)


def _ensure_columns():
    """Lightweight SQLite column migration (create_all only adds missing tables)."""
    wanted = {
        "quote_revisions": [
            ("logistics_cost", "REAL DEFAULT 0"),
            ("logistics_location", "VARCHAR DEFAULT ''"),
            ("status_note", "TEXT DEFAULT ''"),
            ("currency", "VARCHAR DEFAULT 'NGN'"),
            ("fx_rate", "REAL DEFAULT 1"),
        ],
        "users": [
            ("must_change_password", "BOOLEAN DEFAULT 0"),
            ("notify_prefs", "JSON"),
        ],
        "shipments": [
            ("eta_alerts", "JSON"),
            ("clearing_agent_id", "VARCHAR"),
            ("shipping_cost", "JSON"),
            ("clearing_cost", "JSON"),
            ("vendor_payments", "JSON"),
        ],
    }
    if engine.dialect.name != "sqlite":
        return
    with engine.begin() as conn:  # begin() commits the ALTERs
        for table, cols in wanted.items():
            existing = {row[1] for row in conn.exec_driver_sql(f"PRAGMA table_info({table})")}
            for name, ddl in cols:
                if name not in existing:
                    conn.exec_driver_sql(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}")


_ensure_columns()
seed()

app = FastAPI(title="Interdec Platform API", version="1.0.0")

# The Nuxt app calls the API same-origin through its /api proxy, so browsers
# only need CORS for explicitly configured origins. A wildcard origin combined
# with credentials is unsafe, so it is no longer the default.
_origins = [o.strip() for o in os.environ.get(
    "INTERDEC_CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000"
).split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=False,  # auth is a Bearer header, not cookies
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
    expose_headers=["Content-Disposition"],
)

app.include_router(auth_router.router)
app.include_router(activity.router)
app.include_router(users.router)
app.include_router(vendors.router)
app.include_router(shippers.router)
app.include_router(projects.router)
app.include_router(shipments.router)
app.include_router(quotes.router)
app.include_router(settings.router)
app.include_router(exports.router)
app.include_router(clearing_agents.router)
app.include_router(imports.router)


@app.on_event("startup")
def _start_background_jobs():
    eta_alerts.start_scheduler(SessionLocal)


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "interdec-platform-api"}


# --- Production: serve the built Nuxt SPA from the same server -------------
# Set INTERDEC_STATIC_DIR to the `nuxt generate` output (frontend/.output/public).
# Real files are served as-is; any other non-API path (/platform/quotes/...)
# gets index.html so the SPA router can take over. Unset in local dev.
_static_dir = os.environ.get("INTERDEC_STATIC_DIR", "").strip()
if _static_dir and os.path.isdir(_static_dir):
    from pathlib import Path as _P
    from fastapi import HTTPException
    from fastapi.responses import FileResponse

    _root = _P(_static_dir).resolve()
    _index = _root / "200.html" if (_root / "200.html").exists() else _root / "index.html"

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str):
        if full_path.startswith("api/") or full_path == "api":
            raise HTTPException(status_code=404)
        target = (_root / full_path).resolve()
        if full_path and target.is_file() and _root in target.parents:
            return FileResponse(target)
        return FileResponse(_index)

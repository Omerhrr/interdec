"""Interdec Platform — FastAPI backend entrypoint."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from .database import Base, engine
from .seed import seed
from .routers import auth_router, users, vendors, shippers, projects, shipments, activity, quotes

Base.metadata.create_all(bind=engine)


def _ensure_columns():
    """Lightweight SQLite column migration (create_all only adds missing tables)."""
    wanted = {
        "quote_revisions": [
            ("logistics_cost", "REAL DEFAULT 0"),
            ("logistics_location", "VARCHAR DEFAULT ''"),
        ],
    }
    with engine.connect() as conn:
        for table, cols in wanted.items():
            existing = {row[1] for row in conn.exec_driver_sql(f"PRAGMA table_info({table})")}
            for name, ddl in cols:
                if name not in existing:
                    conn.exec_driver_sql(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}")


_ensure_columns()
seed()

app = FastAPI(title="Interdec Platform API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router.router)
app.include_router(activity.router)
app.include_router(users.router)
app.include_router(vendors.router)
app.include_router(shippers.router)
app.include_router(projects.router)
app.include_router(shipments.router)
app.include_router(quotes.router)


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "interdec-platform-api"}

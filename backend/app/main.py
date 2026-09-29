"""Interdec Platform — FastAPI backend entrypoint."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from .database import Base, engine
from .seed import seed
from .routers import auth_router, users, vendors, shippers, projects, shipments

Base.metadata.create_all(bind=engine)
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
app.include_router(users.router)
app.include_router(vendors.router)
app.include_router(shippers.router)
app.include_router(projects.router)
app.include_router(shipments.router)


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "interdec-platform-api"}

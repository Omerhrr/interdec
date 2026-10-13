"""Database setup — SQLAlchemy engine, session, base."""
import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

# Resolve the SQLite file relative to the backend folder (not the current
# working directory), so starting uvicorn from another folder never silently
# creates a second, empty database. Override with INTERDEC_DATABASE_URL.
_DEFAULT_DB = Path(__file__).resolve().parent.parent / "interdec.db"
SQLALCHEMY_DATABASE_URL = os.environ.get("INTERDEC_DATABASE_URL") or f"sqlite:///{_DEFAULT_DB.as_posix()}"

_connect_args = {"check_same_thread": False} if SQLALCHEMY_DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args=_connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

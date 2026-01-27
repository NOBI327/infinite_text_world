"""Health check endpoint."""

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.db.database import get_db

router = APIRouter()


@router.get("/health")
def health_check(db: Session = Depends(get_db)) -> dict[str, str]:
    """Return application and database health status."""
    try:
        db.execute(text("SELECT 1"))
        return {"status": "ok", "database": "connected"}
    except Exception:
        return {"status": "error", "database": "disconnected"}

from fastapi import APIRouter
from sqlalchemy import text

from app import __version__
from app.api.deps import DbSession
from app.core.config import settings

router = APIRouter(tags=["system"])


@router.get("/health")
def health(db: DbSession) -> dict:
    db.execute(text("SELECT 1"))
    return {"status": "ok", "app": settings.app_name, "version": __version__, "database": "ok"}


@router.get("/config")
def public_config() -> dict:
    """Non-sensitive configuration the frontend needs at startup."""
    return {
        "default_location": {
            "name": settings.default_location_name,
            "latitude": settings.default_latitude,
            "longitude": settings.default_longitude,
        },
        "default_radius_km": settings.default_radius_km,
        "allowed_radii_km": settings.allowed_radii_km,
        "footfall_data_notice": "Synthetic footfall data — POC",
    }

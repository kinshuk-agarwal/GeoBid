from fastapi import APIRouter

from app.api.deps import AdminUser, DbSession
from app.core.config import settings
from app.footfall import get_footfall_provider
from app.schemas.pole import FootfallSourceOut, RefreshOut
from app.services import footfall_service

router = APIRouter(prefix="/footfall", tags=["footfall"])


@router.get("/source", response_model=FootfallSourceOut)
def footfall_source() -> FootfallSourceOut:
    """Which provider supplies footfall, and the classification shares in use."""
    return FootfallSourceOut(
        **get_footfall_provider().info(),
        high_share=settings.footfall_high_share,
        medium_share=settings.footfall_medium_share,
    )


@router.post("/refresh", response_model=RefreshOut)
def refresh_footfall(db: DbSession, _admin: AdminUser) -> RefreshOut:
    """Re-import footfall from the provider and recompute categories."""
    result = footfall_service.refresh_from_provider(db, get_footfall_provider())
    return RefreshOut(source=result.source, updated=result.updated, missing=result.missing)

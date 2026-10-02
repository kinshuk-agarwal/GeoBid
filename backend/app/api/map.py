from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import DbSession
from app.core.config import settings
from app.models import FootfallCategory
from app.schemas.pole import MapResponse, PoleOut
from app.services import map_service
from app.services.pole_service import PoleFilters

router = APIRouter(prefix="/map", tags=["map"])

Lat = Annotated[float, Query(ge=-90, le=90)]
Lng = Annotated[float, Query(ge=-180, le=180)]
Radius = Annotated[float, Query(gt=0, le=50, description="Radius in km")]


@router.get("/poles", response_model=MapResponse)
def map_poles(
    db: DbSession,
    latitude: Lat = settings.default_latitude,
    longitude: Lng = settings.default_longitude,
    radius_km: Radius = settings.default_radius_km,
    category: FootfallCategory | None = None,
    min_footfall: Annotated[int | None, Query(ge=0)] = None,
    min_score: Annotated[int | None, Query(ge=0, le=100)] = None,
    top_limit: Annotated[int, Query(ge=1, le=20)] = 5,
) -> MapResponse:
    """Everything the map needs: roads, poles in radius, top poles per category."""
    filters = PoleFilters(category=category, min_footfall=min_footfall, min_score=min_score)
    return map_service.map_view(db, latitude, longitude, radius_km, filters, top_limit)


@router.get("/poles/nearby", response_model=list[PoleOut])
def nearby_poles(
    db: DbSession,
    latitude: Lat,
    longitude: Lng,
    radius_km: Radius = 2.0,
    limit: Annotated[int, Query(ge=1, le=100)] = 10,
) -> list[PoleOut]:
    """Poles closest to a point, nearest first."""
    poles = map_service.poles_within(db, latitude, longitude, radius_km)
    return sorted(poles, key=lambda p: p.distance_km or 0)[:limit]

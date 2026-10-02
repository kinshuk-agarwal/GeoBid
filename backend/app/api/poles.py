from typing import Annotated

from fastapi import APIRouter, Query, status

from app.api.deps import AdminUser, DbSession
from app.models import FootfallCategory
from app.schemas.pole import PoleCreate, PoleOut, PoleUpdate, RoadOut
from app.services import footfall_service, pole_service
from app.services.pole_service import PoleFilters

router = APIRouter(tags=["poles"])


@router.get("/roads", response_model=list[RoadOut])
def list_roads(db: DbSession) -> list[RoadOut]:
    return pole_service.list_roads(db)


@router.get("/poles", response_model=list[PoleOut])
def list_poles(
    db: DbSession,
    category: FootfallCategory | None = None,
    min_footfall: Annotated[int | None, Query(ge=0)] = None,
    min_score: Annotated[int | None, Query(ge=0, le=100)] = None,
    road_id: int | None = None,
    owner_id: int | None = None,
    include_inactive: bool = False,
) -> list[PoleOut]:
    filters = PoleFilters(category, min_footfall, min_score, road_id, owner_id, include_inactive)
    ranks = footfall_service.compute_rankings(db)
    return [pole_service.to_pole_out(p, ranks) for p in pole_service.list_poles(db, filters)]


@router.get("/poles/{pole_id}", response_model=PoleOut)
def get_pole(pole_id: str, db: DbSession) -> PoleOut:
    """``pole_id`` may be the numeric id or the pole code (e.g. ``P014``)."""
    pole = pole_service.get_pole(db, pole_id)
    return pole_service.to_pole_out(pole, footfall_service.compute_rankings(db))


@router.post("/poles", response_model=PoleOut, status_code=status.HTTP_201_CREATED)
def create_pole(body: PoleCreate, db: DbSession, _admin: AdminUser) -> PoleOut:
    pole = pole_service.create_pole(db, body)
    return pole_service.to_pole_out(pole, footfall_service.compute_rankings(db))


@router.put("/poles/{pole_id}", response_model=PoleOut)
def update_pole(pole_id: str, body: PoleUpdate, db: DbSession, _admin: AdminUser) -> PoleOut:
    pole = pole_service.update_pole(db, pole_id, body)
    return pole_service.to_pole_out(pole, footfall_service.compute_rankings(db))


@router.delete("/poles/{pole_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_pole(pole_id: str, db: DbSession, _admin: AdminUser) -> None:
    pole_service.delete_pole(db, pole_id)

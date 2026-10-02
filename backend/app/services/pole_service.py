"""Pole and road queries plus admin CRUD."""

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.exceptions import BusinessRuleError, ConflictError, NotFoundError
from app.footfall import get_footfall_provider
from app.models import (
    Auction,
    AuctionStatus,
    FootfallCategory,
    InventorySlot,
    Pole,
    PoleStatus,
    Road,
    SlotStatus,
    User,
    UserRole,
)
from app.schemas.pole import PoleCreate, PoleOut, PoleUpdate, RoadOut
from app.services import footfall_service
from app.services.footfall_ranking import PoleRank
from app.utils.time import utcnow


@dataclass
class PoleFilters:
    category: FootfallCategory | None = None
    min_footfall: int | None = None
    min_score: int | None = None
    road_id: int | None = None
    owner_id: int | None = None
    include_inactive: bool = False


def to_pole_out(pole: Pole, ranks: dict[int, PoleRank], distance_km: float | None = None) -> PoleOut:
    r = ranks.get(pole.id)
    return PoleOut(
        id=pole.id,
        code=pole.code,
        name=pole.name,
        road_id=pole.road_id,
        road_name=pole.road.name if pole.road else None,
        owner_id=pole.owner_id,
        owner_name=pole.owner.name if pole.owner else None,
        latitude=pole.latitude,
        longitude=pole.longitude,
        footfall=pole.footfall,
        footfall_score=pole.footfall_score,
        visibility_score=pole.visibility_score,
        footfall_source=pole.footfall_source,
        footfall_updated_at=pole.footfall_updated_at,
        category=pole.category,
        status=pole.status,
        rank=r.rank if r else None,
        category_rank=r.category_rank if r else None,
        percentile=r.percentile if r else None,
        distance_km=round(distance_km, 2) if distance_km is not None else None,
    )


def _pole_query():
    return select(Pole).options(selectinload(Pole.road), selectinload(Pole.owner))


def list_poles(db: Session, f: PoleFilters) -> list[Pole]:
    q = _pole_query()
    if not f.include_inactive:
        q = q.where(Pole.status == PoleStatus.ACTIVE)
    if f.category:
        q = q.where(Pole.category == f.category)
    if f.min_footfall is not None:
        q = q.where(Pole.footfall >= f.min_footfall)
    if f.min_score is not None:
        q = q.where(Pole.footfall_score >= f.min_score)
    if f.road_id is not None:
        q = q.where(Pole.road_id == f.road_id)
    if f.owner_id is not None:
        q = q.where(Pole.owner_id == f.owner_id)
    return list(db.scalars(q.order_by(Pole.footfall.desc(), Pole.code)))


def get_pole(db: Session, ident: str | int) -> Pole:
    """Look up a pole by numeric id or by code (e.g. ``P014``)."""
    q = _pole_query()
    if isinstance(ident, int) or str(ident).isdigit():
        pole = db.scalar(q.where(Pole.id == int(ident)))
    else:
        pole = db.scalar(q.where(Pole.code == str(ident).upper()))
    if pole is None:
        raise NotFoundError(f"Pole {ident} not found")
    return pole


def list_roads(db: Session) -> list[RoadOut]:
    counts = dict(
        db.execute(
            select(Pole.road_id, func.count(Pole.id))
            .where(Pole.status == PoleStatus.ACTIVE)
            .group_by(Pole.road_id)
        ).all()
    )
    roads = db.scalars(select(Road).order_by(Road.importance_score.desc()))
    return [
        RoadOut.model_validate(r).model_copy(update={"pole_count": counts.get(r.id, 0)})
        for r in roads
    ]


def _validate_refs(db: Session, road_id: int | None, owner_id: int | None) -> None:
    if road_id is not None and db.get(Road, road_id) is None:
        raise NotFoundError(f"Road {road_id} not found")
    if owner_id is not None:
        owner = db.get(User, owner_id)
        if owner is None or owner.role != UserRole.OWNER:
            raise BusinessRuleError(f"User {owner_id} is not a pole owner")


def create_pole(db: Session, data: PoleCreate) -> Pole:
    if db.scalar(select(Pole).where(Pole.code == data.code)):
        raise ConflictError(f"Pole code {data.code} already exists")
    _validate_refs(db, data.road_id, data.owner_id)

    pole = Pole(
        code=data.code,
        name=data.name,
        road_id=data.road_id,
        owner_id=data.owner_id,
        latitude=data.latitude,
        longitude=data.longitude,
    )
    if data.footfall is not None:
        pole.footfall = data.footfall
        pole.footfall_score = data.footfall_score or 0
        pole.visibility_score = data.visibility_score or 0
        pole.footfall_source = "manual"
        pole.footfall_updated_at = utcnow()
    else:
        provider = get_footfall_provider()
        reading = provider.get_readings([data.code]).get(data.code)
        if reading is None:
            raise BusinessRuleError(
                f"The footfall provider has no reading for {data.code}; supply footfall values manually"
            )
        pole.footfall = reading.footfall
        pole.footfall_score = reading.footfall_score
        pole.visibility_score = reading.visibility_score
        pole.footfall_source = provider.source_name
        pole.footfall_updated_at = utcnow()

    db.add(pole)
    footfall_service.recompute_categories(db)
    return get_pole(db, pole.id)


def update_pole(db: Session, ident: str | int, data: PoleUpdate) -> Pole:
    pole = get_pole(db, ident)
    changes = data.model_dump(exclude_unset=True)
    _validate_refs(db, changes.get("road_id"), changes.get("owner_id"))

    footfall_fields = {"footfall", "footfall_score", "visibility_score"}
    for key, value in changes.items():
        if key in footfall_fields and value is None:
            continue
        setattr(pole, key, value)
    if footfall_fields & {k for k, v in changes.items() if v is not None}:
        pole.footfall_source = "manual"
        pole.footfall_updated_at = utcnow()

    footfall_service.recompute_categories(db)
    return get_pole(db, pole.id)


def delete_pole(db: Session, ident: str | int) -> None:
    pole = get_pole(db, ident)
    blocking = db.scalar(
        select(func.count(Auction.id))
        .join(InventorySlot, Auction.inventory_slot_id == InventorySlot.id)
        .where(InventorySlot.pole_id == pole.id)
        .where(
            (Auction.status.in_([AuctionStatus.LIVE, AuctionStatus.SCHEDULED]))
            | (InventorySlot.status == SlotStatus.SOLD)
        )
    )
    if blocking:
        raise BusinessRuleError(
            "Pole has scheduled/live auctions or sold inventory; deactivate it instead"
        )
    db.delete(pole)
    footfall_service.recompute_categories(db)

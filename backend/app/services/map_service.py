"""Radius-based pole discovery for the map view."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import FootfallCategory, Road
from app.schemas.pole import DataNotice, MapCenter, MapResponse, PoleOut, RoadOut, TopPoles
from app.services import footfall_service, pole_service
from app.services.pole_service import PoleFilters
from app.utils.geo import haversine_km

FOOTFALL_NOTICE = "Synthetic footfall data — POC. Values simulate an upstream model, not real measurements."
GEOGRAPHY_NOTICE = (
    "Road alignments approximate real corridors around Kondapur; pole sites are fictional."
)


def poles_within(
    db: Session, lat: float, lng: float, radius_km: float, filters: PoleFilters | None = None
) -> list[PoleOut]:
    """Active poles within ``radius_km``, highest footfall first.

    Categories and ranks are relative to the whole market, not just the
    visible radius, so a pole keeps its colour when the radius changes.
    """
    ranks = footfall_service.compute_rankings(db)
    out = []
    for pole in pole_service.list_poles(db, filters or PoleFilters()):
        d = haversine_km(lat, lng, pole.latitude, pole.longitude)
        if d <= radius_km:
            out.append(pole_service.to_pole_out(pole, ranks, distance_km=d))
    return out


def roads_within(db: Session, lat: float, lng: float, radius_km: float) -> list[RoadOut]:
    """Roads with at least one vertex inside the radius (returned whole)."""
    all_roads = {r.id: r for r in pole_service.list_roads(db)}
    ids = [
        road.id
        for road in db.scalars(select(Road))
        if any(haversine_km(lat, lng, p[0], p[1]) <= radius_km for p in road.path)
    ]
    return sorted((all_roads[i] for i in ids), key=lambda r: -r.importance_score)


def top_by_category(poles: list[PoleOut], limit: int) -> TopPoles:
    grouped: dict[FootfallCategory, list[PoleOut]] = {c: [] for c in FootfallCategory}
    for p in sorted(poles, key=lambda p: -p.footfall):
        if len(grouped[p.category]) < limit:
            grouped[p.category].append(p)
    return TopPoles(**{c.value: v for c, v in grouped.items()})


def map_view(
    db: Session, lat: float, lng: float, radius_km: float, filters: PoleFilters, top_limit: int = 5
) -> MapResponse:
    poles = poles_within(db, lat, lng, radius_km, filters)
    counts = {c.value: 0 for c in FootfallCategory}
    for p in poles:
        counts[p.category.value] += 1
    counts["total"] = len(poles)
    return MapResponse(
        center=MapCenter(latitude=lat, longitude=lng),
        radius_km=radius_km,
        roads=roads_within(db, lat, lng, radius_km),
        poles=poles,
        top=top_by_category(poles, top_limit),
        counts=counts,
        notice=DataNotice(footfall=FOOTFALL_NOTICE, geography=GEOGRAPHY_NOTICE),
    )

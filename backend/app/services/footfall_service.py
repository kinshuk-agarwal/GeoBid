"""Applies footfall from a provider to poles and maintains categories."""

from dataclasses import dataclass

from sqlalchemy import delete, insert, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.footfall import FootfallProvider
from app.models import Pole, PoleFootfallProfile, PoleStatus
from app.services.footfall_ranking import PoleRank, classify_footfall
from app.utils.time import utcnow


@dataclass
class RefreshResult:
    source: str
    updated: int
    missing: list[str]


def _active_poles(db: Session) -> list[Pole]:
    return list(db.scalars(select(Pole).where(Pole.status == PoleStatus.ACTIVE)))


def compute_rankings(db: Session) -> dict[int, PoleRank]:
    """Rank all active poles by footfall. Cheap at POC scale (tens of poles)."""
    poles = _active_poles(db)
    return classify_footfall(
        {p.id: p.footfall for p in poles},
        settings.footfall_high_share,
        settings.footfall_medium_share,
    )


def recompute_categories(db: Session, *, commit: bool = True) -> dict[int, PoleRank]:
    """Persist each active pole's category from the current distribution."""
    db.flush()
    ranks = compute_rankings(db)
    for pole in _active_poles(db):
        pole.category = ranks[pole.id].category
    if commit:
        db.commit()
    return ranks


def refresh_from_provider(db: Session, provider: FootfallProvider) -> RefreshResult:
    poles = list(db.scalars(select(Pole)))
    readings = provider.get_readings(p.code for p in poles)
    now = utcnow()
    missing: list[str] = []
    for pole in poles:
        reading = readings.get(pole.code)
        if reading is None:
            missing.append(pole.code)
            continue
        pole.footfall = reading.footfall
        pole.footfall_score = reading.footfall_score
        pole.visibility_score = reading.visibility_score
        pole.footfall_source = provider.source_name
        pole.footfall_updated_at = now
    _store_hourly_profiles(db, poles, provider)
    recompute_categories(db)
    return RefreshResult(source=provider.source_name, updated=len(poles) - len(missing), missing=missing)


def _store_hourly_profiles(db: Session, poles: list[Pole], provider: FootfallProvider) -> None:
    """Replace stored time-of-day profiles with the provider's (if it has any)."""
    profiles = provider.get_hourly_profiles(p.code for p in poles)
    by_code = {p.code: p for p in poles}
    for code, profile in profiles.items():
        pole = by_code[code]
        db.execute(delete(PoleFootfallProfile).where(PoleFootfallProfile.pole_id == pole.id))
        if profile:
            db.execute(
                insert(PoleFootfallProfile),
                [{"pole_id": pole.id, "weekday": wd, "hour": h, "footfall": v} for (wd, h), v in profile.items()],
            )

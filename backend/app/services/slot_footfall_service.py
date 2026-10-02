"""Footfall per advertising slot, from the provider's hourly profiles.

A slot's footfall is the sum of the hourly footfall inside its window on the
slot date's weekday, so it adapts to however shifts are configured.
"""

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import PoleFootfallProfile
from app.services import shifts as shift_svc

Profile = dict[tuple[int, int], int]  # (weekday Monday=0, hour) -> footfall


def load_profiles(db: Session, pole_ids: list[int]) -> dict[int, Profile]:
    out: dict[int, Profile] = {}
    if not pole_ids:
        return out
    rows = db.execute(
        select(
            PoleFootfallProfile.pole_id, PoleFootfallProfile.weekday, PoleFootfallProfile.hour, PoleFootfallProfile.footfall
        ).where(PoleFootfallProfile.pole_id.in_(pole_ids))
    )
    for pole_id, wd, h, v in rows:
        out.setdefault(pole_id, {})[(wd, h)] = v
    return out


def shift_footfall(profile: Profile | None, day: date, shift_code: str) -> int | None:
    """Footfall during one shift on ``day``. ``None`` if no profile is available."""
    if not profile:
        return None
    s = shift_svc.get_shift(shift_code)
    hours = (s.end.hour - s.start.hour) % 24 or 24
    wd = day.weekday()
    return sum(
        profile.get(((wd + (s.start.hour + i) // 24) % 7, (s.start.hour + i) % 24), 0) for i in range(hours)
    )


def day_total(profile: Profile, weekday: int) -> int:
    return sum(v for (wd, _h), v in profile.items() if wd == weekday)

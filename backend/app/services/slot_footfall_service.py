"""Footfall per advertising slot, from the provider's hourly profiles.

A slot's footfall is the sum of the hourly footfall inside its window on the
slot date's weekday, so it adapts to however shifts are configured.
"""

import hashlib
import random
from datetime import date, datetime

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


# The forecast is shown as a ±FORECAST_BAND range. Most measured counts land
# inside it (within ±ACTUAL_DEVIATION); about MISS_RATE of slots miss it by a
# little (MISS_MIN-MISS_MAX off the forecast), as real forecasts sometimes do.
FORECAST_BAND = 0.10
ACTUAL_DEVIATION = 0.08
MISS_RATE = 0.2
MISS_MIN, MISS_MAX = 0.11, 0.16


def forecast_range(predicted: int) -> tuple[int, int]:
    """±FORECAST_BAND around the forecast, widened to tidy numbers (10s below 1,000, else 50s)."""
    step = 10 if predicted < 1000 else 50
    low = int(predicted * (1 - FORECAST_BAND) // step * step)
    high = int(-(-predicted * (1 + FORECAST_BAND) // step) * step)
    return low, high


def actual_footfall(predicted: int, pole_code: str, day: date, shift_code: str) -> int:
    """POC stand-in for a measured count, close to the forecast and fixed per
    pole, date and slot (the same on every call). Usually inside the forecast
    range; sometimes a small miss (see MISS_RATE)."""
    seed = int.from_bytes(hashlib.sha256(f"{pole_code}|{day.isoformat()}|{shift_code}".encode()).digest()[:8], "big")
    rng = random.Random(seed)
    if rng.random() < MISS_RATE:
        off = rng.uniform(MISS_MIN, MISS_MAX) * rng.choice((-1, 1))
    else:
        off = rng.uniform(-ACTUAL_DEVIATION, ACTUAL_DEVIATION)
    return max(0, round(predicted * (1 + off)))


def measured(predicted: int, pole_code: str, day: date, shift_code: str, now: datetime) -> tuple[str, int | None]:
    """Where a slot stands at ``now`` and its measured footfall so far:
    ("upcoming", None) before it starts, ("live", count so far) while it runs,
    ("done", final count) after it ends."""
    start, end = shift_svc.shift_window(day, shift_code)
    if now < start:
        return "upcoming", None
    total = actual_footfall(predicted, pole_code, day, shift_code)
    if now >= end:
        return "done", total
    return "live", round(total * (now - start) / (end - start))


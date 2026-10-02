"""Configurable daily advertising shifts and local-time helpers."""

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone

from app.core.config import settings
from app.core.exceptions import NotFoundError
from app.utils.time import utcnow


@dataclass(frozen=True)
class Shift:
    code: str
    start: time
    end: time
    demand: str
    multiplier: float

    @property
    def label(self) -> str:
        return f"{self.start:%H:%M}–{self.end:%H:%M}"


def local_tz() -> timezone:
    return timezone(timedelta(minutes=settings.utc_offset_minutes))


def local_today() -> date:
    return utcnow().astimezone(local_tz()).date()


def tomorrow() -> date:
    return local_today() + timedelta(days=1)


def list_shifts() -> list[Shift]:
    shifts = []
    for s in settings.shifts:
        if s.demand not in settings.demand_multipliers:
            raise ValueError(f"Shift {s.code}: unknown demand level {s.demand!r}")
        shifts.append(
            Shift(
                code=s.code,
                start=time.fromisoformat(s.start),
                end=time.fromisoformat(s.end),
                demand=s.demand,
                multiplier=settings.demand_multipliers[s.demand],
            )
        )
    return shifts


def get_shift(code: str) -> Shift:
    for s in list_shifts():
        if s.code == code:
            return s
    raise NotFoundError(f"Unknown shift {code!r}")


def shift_window(day: date, code: str) -> tuple[datetime, datetime]:
    """UTC start/end of a shift on a local calendar day."""
    shift = get_shift(code)
    tz = local_tz()
    start = datetime.combine(day, shift.start, tz)
    end_day = day if shift.end > shift.start else day + timedelta(days=1)
    end = datetime.combine(end_day, shift.end, tz)
    return start.astimezone(timezone.utc), end.astimezone(timezone.utc)

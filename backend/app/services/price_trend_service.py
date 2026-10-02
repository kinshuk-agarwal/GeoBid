"""Price trends and expected-price ranges from past winning prices.

The expected price for a slot is the average winning price of the same pole
and 2-hour shift on the same weekday over the look-back window (default 60
days), shown as a rounded range: e.g. 425 -> 400-450, 9,430 -> 9,000-10,000.
"""

import math
from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import Pole
from app.models.price_history import SlotPriceHistory
from app.services import shifts as shift_svc

WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
NICE_STEPS = [10, 25, 50, 100, 250, 500, 1_000, 2_500, 5_000, 10_000, 25_000, 50_000]


def price_range(value: float) -> tuple[int, int]:
    """Bucket a price into a readable range about 10% wide.

    The step is the largest "nice" number no more than 12% of the value:
    425 -> (400, 450); 9,430 -> (9,000, 10,000); 16,300 -> (16,000, 17,000).
    """
    if value <= 0:
        return (0, 0)
    step = max([s for s in NICE_STEPS if s <= value * 0.12] or [NICE_STEPS[0]])
    low = int(math.floor(value / step) * step)
    return (low, low + step)


@dataclass(frozen=True)
class ExpectedPrice:
    weekday: int  # Monday=0
    average: int
    low: int
    high: int
    min_price: int
    max_price: int
    samples: int  # days with a sale
    days: int  # days observed (sold + unsold)

    @property
    def weekday_label(self) -> str:
        return WEEKDAYS[self.weekday]


def _window(today: date | None = None) -> tuple[date, date]:
    today = today or shift_svc.local_today()
    return today - timedelta(days=settings.price_trend_days), today


def _sqlite_weekday_to_python(w: str | int) -> int:
    return (int(w) + 6) % 7  # SQLite %w: Sunday=0


def expected_prices(db: Session, pole_ids: list[int]) -> dict[tuple[int, str, int], ExpectedPrice]:
    """Expected price per (pole_id, shift, weekday) for the given poles, in one query."""
    if not pole_ids:
        return {}
    start, end = _window()
    wd = func.strftime("%w", SlotPriceHistory.date)
    rows = db.execute(
        select(
            SlotPriceHistory.pole_id,
            SlotPriceHistory.shift,
            wd,
            func.avg(SlotPriceHistory.clearing_price),
            func.min(SlotPriceHistory.clearing_price),
            func.max(SlotPriceHistory.clearing_price),
            func.count(SlotPriceHistory.clearing_price),
            func.count(SlotPriceHistory.id),
        )
        .where(SlotPriceHistory.pole_id.in_(pole_ids), SlotPriceHistory.date >= start, SlotPriceHistory.date < end)
        .group_by(SlotPriceHistory.pole_id, SlotPriceHistory.shift, wd)
    ).all()
    out: dict[tuple[int, str, int], ExpectedPrice] = {}
    for pole_id, shift, w, avg, lo, hi, sold, total in rows:
        if not sold:
            continue
        weekday = _sqlite_weekday_to_python(w)
        low, high = price_range(avg)
        out[(pole_id, shift, weekday)] = ExpectedPrice(
            weekday, int(round(avg)), low, high, int(lo), int(hi), int(sold), int(total)
        )
    return out


def expected_for(table: dict, pole_id: int, shift: str, day: date) -> ExpectedPrice | None:
    return table.get((pole_id, shift, day.weekday()))


@dataclass
class TrendPoint:
    date: date
    weekday: int
    clearing_price: int | None
    base_price: int
    source: str


def trend(db: Session, pole: Pole, shift: str) -> list[TrendPoint]:
    start, end = _window()
    rows = db.scalars(
        select(SlotPriceHistory)
        .where(
            SlotPriceHistory.pole_id == pole.id,
            SlotPriceHistory.shift == shift,
            SlotPriceHistory.date >= start,
            SlotPriceHistory.date < end,
        )
        .order_by(SlotPriceHistory.date)
    )
    return [TrendPoint(r.date, r.date.weekday(), r.clearing_price, r.base_price, r.source) for r in rows]

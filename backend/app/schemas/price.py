from datetime import date

from pydantic import BaseModel

from app.schemas.auction import ExpectedPriceOut


class TrendPointOut(BaseModel):
    date: date
    weekday: str
    clearing_price: int | None  # null = unsold that day
    base_price: int
    source: str  # "auction" | "synthetic"


class WeekdayStatOut(BaseModel):
    weekday: str
    average: int | None
    low: int | None
    high: int | None
    samples: int
    days: int


class PriceTrendOut(BaseModel):
    pole_code: str
    shift: str
    shift_label: str
    demand: str
    window_days: int
    points: list[TrendPointOut]
    by_weekday: list[WeekdayStatOut]  # Monday first
    target_date: date
    expected: ExpectedPriceOut | None  # same weekday as target_date
    overall_average: int | None
    sell_through: float  # share of days that sold
    synthetic_share: float  # share of points that are synthetic back-fill

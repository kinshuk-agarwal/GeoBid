from datetime import date

from pydantic import BaseModel


class SlotFootfallOut(BaseModel):
    shift: str
    label: str
    demand: str
    footfall: int
    share: float  # of the day's total


class WeekdayFootfallOut(BaseModel):
    weekday: str
    total: int


class FootfallProfileOut(BaseModel):
    pole_code: str
    date: date
    weekday: str
    daily_total: int
    peak_shift: str | None
    slots: list[SlotFootfallOut]
    by_weekday: list[WeekdayFootfallOut]  # Monday first
    source: str

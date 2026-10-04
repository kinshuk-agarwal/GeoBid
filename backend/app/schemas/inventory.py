from datetime import date, datetime

from pydantic import BaseModel, Field

from app.models.enums import FootfallCategory, SlotStatus
from app.schemas.auction import AuctionBrief, ExpectedPriceOut


class ShiftOut(BaseModel):
    code: str
    label: str
    start: str
    end: str
    demand: str
    multiplier: float


class TariffBreakdown(BaseModel):
    base_rate: int
    pole_value: float
    pole_multiplier: float
    shift_multiplier: float
    demand: str
    base_tariff: int
    reserve_price: int
    basis: str = "demand_table"  # or "slot_footfall"
    slot_footfall: int | None = None
    avg_slot_footfall: int | None = None


class SlotOut(BaseModel):
    id: int
    pole_id: int
    pole_code: str
    pole_name: str
    pole_category: FootfallCategory
    footfall: int
    date: date
    shift: str
    shift_label: str
    demand: str
    start_time: datetime
    end_time: datetime
    base_tariff: int
    reserve_price: int
    status: SlotStatus
    tariff: TariffBreakdown
    auction: AuctionBrief | None = None
    expected_price: ExpectedPriceOut | None = None
    # Footfall during this slot on this date's weekday (from the hourly profile).
    slot_footfall: int | None = None


class SlotCreate(BaseModel):
    pole_id: int
    date: date
    shift: str = Field(examples=["S5"])
    # Optional override; otherwise the tariff engine sets the reserve price.
    reserve_price: int | None = Field(default=None, gt=0)


class PoleInventoryOut(BaseModel):
    pole_id: int
    pole_code: str
    date: date
    is_tomorrow: bool
    market_status: str  # AVAILABLE | AUCTIONING | SOLD_OUT | NO_INVENTORY
    slots: list[SlotOut]


class AuctionRulesOut(BaseModel):
    seats_per_slot: int
    confirmed_seats: int
    min_increment: int
    premium_floor_multiplier: float
    qualifying_close_time: str  # the day before the ad date
    premium_round_start_time: str  # the day before the ad date
    premium_close_before_slot_minutes: int


class TariffConfigOut(BaseModel):
    formula: str
    base_rate: int
    footfall_weight: float
    visibility_weight: float
    pole_multiplier_min: float
    pole_multiplier_max: float
    rounding: int
    slot_footfall_exponent: float
    slot_multiplier_min: float
    slot_multiplier_max: float
    demand_multipliers: dict[str, float]
    shifts: list[ShiftOut]
    timezone_offset_minutes: int
    auction: AuctionRulesOut
    note: str

"""Tariff engine: base price (reserve) for one pole-slot (pure functions).

    pole_value       = w_f x footfall_score + w_v x visibility_score      (0-100)
    pole_multiplier  = min + (max - min) x pole_value / 100
    avg_slot         = pole's average daily footfall x slot_hours / 24
    slot_multiplier  = clamp((slot_footfall / avg_slot) ^ exponent, lo, hi)
    base_price       = base_rate x pole_multiplier x slot_multiplier   (rounded)

The slot multiplier uses the footfall model's footfall for that pole, slot and
weekday, so a pole's busiest slots cost the most. Without a time-of-day
profile it falls back to the shift's configured demand multiplier.

This is a transparent POC business rule, not an industry pricing standard.
The base price is only the auction's starting point; bidding sets the price.
"""

from dataclasses import dataclass

from app.core.config import settings
from app.services.shifts import Shift, get_shift

# Footfall ratio (slot vs. the pole's average slot) -> demand label.
DEMAND_BANDS = [(0.5, "LOW"), (0.8, "LOW_MEDIUM"), (1.2, "MEDIUM"), (1.6, "HIGH")]


@dataclass(frozen=True)
class TariffQuote:
    base_rate: int
    pole_value: float
    pole_multiplier: float
    shift_code: str
    demand: str
    shift_multiplier: float  # the slot multiplier, whichever basis produced it
    base_tariff: int
    reserve_price: int
    basis: str  # "slot_footfall" | "demand_table"
    slot_footfall: int | None = None
    avg_slot_footfall: int | None = None


def pole_value(footfall_score: int, visibility_score: int) -> float:
    v = settings.tariff_footfall_weight * footfall_score + settings.tariff_visibility_weight * visibility_score
    return round(min(max(v, 0.0), 100.0), 1)


def pole_multiplier(value: float) -> float:
    lo, hi = settings.pole_multiplier_min, settings.pole_multiplier_max
    return round(lo + (hi - lo) * value / 100, 3)


def round_price(amount: float) -> int:
    step = max(settings.reserve_rounding_inr, 1)
    return int(round(amount / step) * step)


def _slot_hours(shift: Shift) -> int:
    return (shift.end.hour - shift.start.hour) % 24 or 24


def avg_slot_footfall(daily_footfall: int, shift_code: str) -> float:
    return daily_footfall * _slot_hours(get_shift(shift_code)) / 24


def slot_multiplier(slot_footfall: int, avg_slot: float) -> float:
    if avg_slot <= 0:
        return 1.0
    m = (slot_footfall / avg_slot) ** settings.slot_footfall_exponent
    return round(min(max(m, settings.slot_multiplier_min), settings.slot_multiplier_max), 3)


def demand_level(ratio: float) -> str:
    for limit, label in DEMAND_BANDS:
        if ratio < limit:
            return label
    return "VERY_HIGH"


def slot_demand(slot_footfall: int | None, daily_footfall: int, shift_code: str) -> str:
    """Demand label for a slot: from its footfall when known, else the shift config."""
    if slot_footfall is None or daily_footfall <= 0:
        return get_shift(shift_code).demand
    return demand_level(slot_footfall / avg_slot_footfall(daily_footfall, shift_code))


def quote(
    footfall_score: int,
    visibility_score: int,
    shift_code: str,
    slot_footfall: int | None = None,
    daily_footfall: int | None = None,
) -> TariffQuote:
    """Base price for a slot. Pass ``slot_footfall`` and the pole's
    ``daily_footfall`` to price by the slot's footfall."""
    shift = get_shift(shift_code)
    value = pole_value(footfall_score, visibility_score)
    mult = pole_multiplier(value)
    base_tariff = round(settings.base_tariff_inr * mult)

    if slot_footfall is not None and daily_footfall:
        avg = avg_slot_footfall(daily_footfall, shift_code)
        s_mult = slot_multiplier(slot_footfall, avg)
        demand, basis, avg_out = demand_level(slot_footfall / avg), "slot_footfall", round(avg)
    else:
        s_mult, demand, basis, avg_out = shift.multiplier, shift.demand, "demand_table", None

    return TariffQuote(
        base_rate=settings.base_tariff_inr,
        pole_value=value,
        pole_multiplier=mult,
        shift_code=shift.code,
        demand=demand,
        shift_multiplier=s_mult,
        base_tariff=base_tariff,
        reserve_price=round_price(base_tariff * s_mult),
        basis=basis,
        slot_footfall=slot_footfall if basis == "slot_footfall" else None,
        avg_slot_footfall=avg_out,
    )

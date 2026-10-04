from datetime import date

from fastapi import APIRouter, status

from app.api.deps import AdminUser, DbSession
from app.core.config import settings
from app.core.exceptions import NotFoundError
from app.models import SlotStatus
from app.schemas.inventory import AuctionRulesOut, PoleInventoryOut, ShiftOut, SlotCreate, SlotOut, TariffConfigOut
from app.schemas.footfall import FootfallProfileOut, SlotFootfallOut, WeekdayFootfallOut
from app.schemas.price import PriceTrendOut, TrendPointOut, WeekdayStatOut
from app.services import inventory_service, pole_service, price_trend_service, slot_footfall_service, tariff_service
from app.services.auction_views import expected_out
from app.services import shifts as shift_svc
from app.services.inventory_service import SlotFilters

router = APIRouter(tags=["inventory"])


@router.get("/inventory", response_model=list[SlotOut])
def list_inventory(
    db: DbSession,
    pole_id: int | None = None,
    date: date | None = None,
    shift: str | None = None,
    status: SlotStatus | None = None,
) -> list[SlotOut]:
    slots = inventory_service.list_slots(db, SlotFilters(pole_id, date, shift, status))
    return inventory_service.slots_out(db, slots)


@router.get("/inventory/{slot_id}", response_model=SlotOut)
def get_inventory(slot_id: int, db: DbSession) -> SlotOut:
    return inventory_service.slots_out(db, [inventory_service.get_slot(db, slot_id)])[0]


@router.post("/inventory", response_model=SlotOut, status_code=status.HTTP_201_CREATED)
def create_inventory(body: SlotCreate, db: DbSession, _admin: AdminUser) -> SlotOut:
    slot = inventory_service.create_slot(db, body.pole_id, body.date, body.shift, body.reserve_price)
    return inventory_service.slots_out(db, [slot])[0]


@router.get("/poles/{pole_id}/inventory", response_model=PoleInventoryOut)
def pole_inventory(pole_id: str, db: DbSession, date: date | None = None) -> PoleInventoryOut:
    """A pole's six shifts for ``date`` (default: tomorrow, local time)."""
    return inventory_service.pole_inventory(db, pole_service.get_pole(db, pole_id), date)


@router.get("/tariff/config", response_model=TariffConfigOut, tags=["tariff"])
def tariff_config() -> TariffConfigOut:
    return TariffConfigOut(
        formula="base_price = base_rate × pole_multiplier × slot_multiplier; "
        "pole_multiplier = min + (max − min) × pole_value / 100; "
        "pole_value = w_f × footfall_score + w_v × visibility_score; "
        "slot_multiplier = clamp((slot_footfall / avg_slot_footfall) ^ exponent, lo, hi), "
        "avg_slot_footfall = daily_footfall × slot_hours / 24 "
        "(falls back to the shift's demand multiplier without a footfall profile)",
        base_rate=settings.base_tariff_inr,
        footfall_weight=settings.tariff_footfall_weight,
        visibility_weight=settings.tariff_visibility_weight,
        pole_multiplier_min=settings.pole_multiplier_min,
        pole_multiplier_max=settings.pole_multiplier_max,
        rounding=settings.reserve_rounding_inr,
        slot_footfall_exponent=settings.slot_footfall_exponent,
        slot_multiplier_min=settings.slot_multiplier_min,
        slot_multiplier_max=settings.slot_multiplier_max,
        demand_multipliers=settings.demand_multipliers,
        shifts=[
            ShiftOut(
                code=s.code,
                label=s.label,
                start=f"{s.start:%H:%M}",
                end=f"{s.end:%H:%M}",
                demand=s.demand,
                multiplier=s.multiplier,
            )
            for s in shift_svc.list_shifts()
        ],
        auction=AuctionRulesOut(
            seats_per_slot=settings.seats_per_slot,
            confirmed_seats=settings.confirmed_seats,
            min_increment=settings.auction_min_increment_inr,
            premium_floor_multiplier=settings.premium_floor_multiplier,
            qualifying_close_time=settings.qualifying_close_time,
            premium_round_start_time=settings.premium_round_start_time,
            premium_close_before_slot_minutes=settings.premium_close_before_slot_minutes,
        ),
        timezone_offset_minutes=settings.utc_offset_minutes,
        note="POC business rule, not an industry pricing standard. The reserve is the "
        "auction's starting point; the final price is set by bidding.",
    )


@router.get("/poles/{pole_id}/price-trend", response_model=PriceTrendOut, tags=["prices"])
def price_trend(pole_id: str, shift: str, db: DbSession, date: date | None = None) -> PriceTrendOut:
    """Past winning prices for one pole and 2-hour shift (default 60 days), the
    average per weekday, and the expected range for ``date``'s weekday
    (default: tomorrow)."""
    pole = pole_service.get_pole(db, pole_id)
    s = shift_svc.get_shift(shift)
    target = date or shift_svc.tomorrow()
    points = price_trend_service.trend(db, pole, s.code)
    table = price_trend_service.expected_prices(db, [pole.id])

    by_weekday = []
    for wd, label in enumerate(price_trend_service.WEEKDAYS):
        e = table.get((pole.id, s.code, wd))
        days = sum(1 for p in points if p.weekday == wd)
        by_weekday.append(
            WeekdayStatOut(
                weekday=label,
                average=e.average if e else None,
                low=e.low if e else None,
                high=e.high if e else None,
                samples=e.samples if e else 0,
                days=days,
            )
        )
    sold = [p.clearing_price for p in points if p.clearing_price is not None]
    return PriceTrendOut(
        pole_code=pole.code,
        shift=s.code,
        shift_label=s.label,
        demand=s.demand,
        window_days=settings.price_trend_days,
        points=[
            TrendPointOut(
                date=p.date,
                weekday=price_trend_service.WEEKDAYS[p.weekday],
                clearing_price=p.clearing_price,
                base_price=p.base_price,
                source=p.source,
            )
            for p in points
        ],
        by_weekday=by_weekday,
        target_date=target,
        expected=expected_out(price_trend_service.expected_for(table, pole.id, s.code, target)),
        overall_average=round(sum(sold) / len(sold)) if sold else None,
        sell_through=round(len(sold) / len(points), 3) if points else 0.0,
        synthetic_share=round(sum(p.source == "synthetic" for p in points) / len(points), 3) if points else 0.0,
    )


@router.get("/poles/{pole_id}/footfall-profile", response_model=FootfallProfileOut, tags=["footfall"])
def footfall_profile(pole_id: str, db: DbSession, date: date | None = None) -> FootfallProfileOut:
    """Footfall in each advertising slot on ``date``'s weekday (default:
    tomorrow), plus daily totals per weekday. From the footfall provider."""
    pole = pole_service.get_pole(db, pole_id)
    day = date or shift_svc.tomorrow()
    profile = slot_footfall_service.load_profiles(db, [pole.id]).get(pole.id)
    if not profile:
        raise NotFoundError(f"No time-of-day footfall profile for {pole.code}")
    shifts = shift_svc.list_shifts()
    per_slot = [(s, slot_footfall_service.shift_footfall(profile, day, s.code) or 0) for s in shifts]
    total = sum(v for _, v in per_slot) or 1
    peak = max(per_slot, key=lambda x: x[1])[0].code if per_slot else None
    return FootfallProfileOut(
        pole_code=pole.code,
        date=day,
        weekday=price_trend_service.WEEKDAYS[day.weekday()],
        daily_total=sum(v for _, v in per_slot),
        peak_shift=peak,
        slots=[
            SlotFootfallOut(
                shift=s.code,
                label=s.label,
                demand=tariff_service.slot_demand(v, pole.footfall, s.code),
                footfall=v,
                share=round(v / total, 4),
            )
            for s, v in per_slot
        ],
        by_weekday=[
            WeekdayFootfallOut(weekday=label, total=slot_footfall_service.day_total(profile, wd))
            for wd, label in enumerate(price_trend_service.WEEKDAYS)
        ],
        source=pole.footfall_source,
    )

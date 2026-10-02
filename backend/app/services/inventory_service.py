"""Advertising inventory: one slot per pole, per date, per shift."""

from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.core.exceptions import BusinessRuleError, ConflictError, NotFoundError
from app.models import InventorySlot, Pole, PoleStatus, SlotStatus
from app.schemas.inventory import PoleInventoryOut, SlotOut, TariffBreakdown
from app.services import price_trend_service, slot_footfall_service, tariff_service
from app.services import shifts as shift_svc
from app.services.auction_service import best_bids_for, bid_counts, seat_state
from app.services.auction_views import auction_brief, expected_out


@dataclass
class SlotFilters:
    pole_id: int | None = None
    day: date | None = None
    shift: str | None = None
    status: SlotStatus | None = None


def quote_slot(pole: Pole, day: date, shift_code: str, profile: slot_footfall_service.Profile | None):
    """Tariff for one pole-slot, priced by the slot's footfall on ``day``'s weekday."""
    sf = slot_footfall_service.shift_footfall(profile, day, shift_code)
    return tariff_service.quote(pole.footfall_score, pole.visibility_score, shift_code, sf, pole.footfall)


def _new_slot(
    pole: Pole,
    day: date,
    shift_code: str,
    reserve_override: int | None = None,
    profile: slot_footfall_service.Profile | None = None,
) -> InventorySlot:
    q = quote_slot(pole, day, shift_code, profile)
    return InventorySlot(
        pole_id=pole.id,
        date=day,
        shift=shift_code,
        base_tariff=q.base_tariff,
        reserve_price=reserve_override or q.reserve_price,
        status=SlotStatus.AVAILABLE,
    )


def ensure_inventory(db: Session, day: date) -> int:
    """Create any missing slots for every active pole on ``day``. Idempotent."""
    shift_codes = [s.code for s in shift_svc.list_shifts()]
    poles = list(db.scalars(select(Pole).where(Pole.status == PoleStatus.ACTIVE)))
    profiles = slot_footfall_service.load_profiles(db, [p.id for p in poles])
    existing = set(
        db.execute(
            select(InventorySlot.pole_id, InventorySlot.shift).where(InventorySlot.date == day)
        ).all()
    )
    created = 0
    for pole in poles:
        for code in shift_codes:
            if (pole.id, code) not in existing:
                db.add(_new_slot(pole, day, code, profile=profiles.get(pole.id)))
                created += 1
    db.commit()
    return created


def ensure_upcoming_inventory(db: Session) -> int:
    """Stock inventory for the next ``inventory_days_ahead`` days."""
    today = shift_svc.local_today()
    return sum(
        ensure_inventory(db, today + timedelta(days=d)) for d in range(1, settings.inventory_days_ahead + 1)
    )


def _slot_query():
    return select(InventorySlot).options(selectinload(InventorySlot.pole), selectinload(InventorySlot.auction))


def list_slots(db: Session, f: SlotFilters) -> list[InventorySlot]:
    q = _slot_query()
    if f.pole_id is not None:
        q = q.where(InventorySlot.pole_id == f.pole_id)
    if f.day is not None:
        q = q.where(InventorySlot.date == f.day)
    if f.shift is not None:
        q = q.where(InventorySlot.shift == f.shift)
    if f.status is not None:
        q = q.where(InventorySlot.status == f.status)
    return list(db.scalars(q.order_by(InventorySlot.date, InventorySlot.pole_id, InventorySlot.shift)))


def get_slot(db: Session, slot_id: int) -> InventorySlot:
    slot = db.scalar(_slot_query().where(InventorySlot.id == slot_id))
    if slot is None:
        raise NotFoundError(f"Inventory slot {slot_id} not found")
    return slot


def create_slot(db: Session, pole_id: int, day: date, shift_code: str, reserve: int | None) -> InventorySlot:
    pole = db.get(Pole, pole_id)
    if pole is None:
        raise NotFoundError(f"Pole {pole_id} not found")
    if pole.status != PoleStatus.ACTIVE:
        raise BusinessRuleError("Cannot create inventory for an inactive pole")
    shift_svc.get_shift(shift_code)  # validates the code
    if day <= shift_svc.local_today():
        raise BusinessRuleError("Inventory can only be created for future dates")

    profile = slot_footfall_service.load_profiles(db, [pole.id]).get(pole.id)
    slot = _new_slot(pole, day, shift_code, reserve, profile)
    db.add(slot)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ConflictError(f"{pole.code} already has inventory for {day} {shift_code}") from None
    return get_slot(db, slot.id)


def to_slot_out(
    slot: InventorySlot, bid_count: int = 0, expected=None, slot_footfall: int | None = None, state=None
) -> SlotOut:
    pole = slot.pole
    shift = shift_svc.get_shift(slot.shift)
    start, end = shift_svc.shift_window(slot.date, slot.shift)
    q = tariff_service.quote(pole.footfall_score, pole.visibility_score, slot.shift, slot_footfall, pole.footfall)
    return SlotOut(
        id=slot.id,
        pole_id=pole.id,
        pole_code=pole.code,
        pole_name=pole.name,
        pole_category=pole.category,
        footfall=pole.footfall,
        date=slot.date,
        shift=slot.shift,
        shift_label=shift.label,
        demand=q.demand,
        start_time=start,
        end_time=end,
        base_tariff=slot.base_tariff,
        reserve_price=slot.reserve_price,
        status=slot.status,
        tariff=TariffBreakdown(
            base_rate=q.base_rate,
            pole_value=q.pole_value,
            pole_multiplier=q.pole_multiplier,
            shift_multiplier=q.shift_multiplier,
            demand=q.demand,
            base_tariff=q.base_tariff,
            reserve_price=q.reserve_price,
            basis=q.basis,
            slot_footfall=q.slot_footfall,
            avg_slot_footfall=q.avg_slot_footfall,
        ),
        auction=auction_brief(slot.auction, bid_count, state) if slot.auction and state else None,
        expected_price=expected,
        slot_footfall=slot_footfall,
    )


def slots_out(db: Session, slots: list[InventorySlot]) -> list[SlotOut]:
    auction_ids = [s.auction.id for s in slots if s.auction]
    counts = bid_counts(db, auction_ids)
    best = best_bids_for(db, auction_ids)
    pole_ids = list({s.pole_id for s in slots})
    table = price_trend_service.expected_prices(db, pole_ids)
    profiles = slot_footfall_service.load_profiles(db, pole_ids)
    return [
        to_slot_out(
            s,
            counts.get(s.auction.id, 0) if s.auction else 0,
            expected_out(price_trend_service.expected_for(table, s.pole_id, s.shift, s.date)),
            slot_footfall_service.shift_footfall(profiles.get(s.pole_id), s.date, s.shift),
            seat_state(db, s.auction, best.get(s.auction.id, [])) if s.auction else None,
        )
        for s in slots
    ]


def pole_inventory(db: Session, pole: Pole, day: date | None = None) -> PoleInventoryOut:
    day = day or shift_svc.tomorrow()
    slots = list_slots(db, SlotFilters(pole_id=pole.id, day=day))
    order = {s.code: i for i, s in enumerate(shift_svc.list_shifts())}
    slots.sort(key=lambda s: order.get(s.shift, 99))

    statuses = {s.status for s in slots}
    if not slots:
        market = "NO_INVENTORY"
    elif SlotStatus.IN_AUCTION in statuses:
        market = "AUCTIONING"
    elif SlotStatus.AVAILABLE in statuses:
        market = "AVAILABLE"
    else:
        market = "SOLD_OUT"

    return PoleInventoryOut(
        pole_id=pole.id,
        pole_code=pole.code,
        date=day,
        is_tomorrow=day == shift_svc.tomorrow(),
        market_status=market,
        slots=slots_out(db, slots),
    )

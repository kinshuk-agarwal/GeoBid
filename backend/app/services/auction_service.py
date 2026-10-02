"""Auction engine: two-round auctions for each slot's 4 rotating ad seats.

    Qualifying round  start → 12:00 on the day before the ad date. Anyone bids;
                      the top 4 bidders hold seats 1-4.
    Break             12:00 → 16:00. Seats 1-2 are confirmed; no bidding.
    Premium round     16:00 → 2 hours before the slot. Anyone (except confirmed
                      holders) bids from 1.5x the top qualifying bid; premium
                      bids take seat 4, then seat 3, then the lowest premium seat.

At the close every seat holder wins and pays their own bid; the ad rotates
equally among them. Bids are at least ``min_increment`` (₹100) apart, so no two
seats hold the same amount. Seat rules live in ``seat_engine`` (pure); this
module adds persistence, timing and events.

The backend is the source of truth. Functions take an explicit ``now`` so
timing is deterministic and testable, and return the ``AuctionEvent``s they
caused; the caller publishes them.
"""

from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import and_, func, select, update
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.core.exceptions import BusinessRuleError, ConflictError, NotFoundError, PermissionDeniedError
from app.models import (
    Auction,
    AuctionRound,
    AuctionStatus,
    Bid,
    ConfirmedSeat,
    InventorySlot,
    Pole,
    SlotPriceHistory,
    SlotStatus,
    User,
    UserRole,
    WinningAdvertisement,
)
from app.services import seat_engine
from app.services import shifts as shift_svc
from app.services.events import AuctionEvent, EventType
from app.services.seat_engine import BestBid, Seat
from app.utils.time import ensure_utc, utcnow

OPEN_STATUSES = (AuctionStatus.SCHEDULED, AuctionStatus.LIVE)


def bidder_alias(user_id: int) -> str:
    """Public label for a bidder. Advertiser names are not shown to rivals."""
    return f"Bidder {user_id}"


def default_min_increment(reserve: int) -> int:
    """Minimum gap between bids. Flat for now; ``reserve`` lets a price-based
    rule be added without changing callers."""
    del reserve
    return settings.auction_min_increment_inr


# --- schedule -----------------------------------------------------------------


@dataclass(frozen=True)
class Schedule:
    start: datetime
    qualifying_end: datetime
    premium_start: datetime
    end: datetime


def _local(day: date, hhmm: str) -> datetime:
    return datetime.combine(day, time.fromisoformat(hhmm), shift_svc.local_tz()).astimezone(timezone.utc)


def default_schedule(slot: InventorySlot, now: datetime) -> Schedule:
    day_before = slot.date - timedelta(days=1)
    slot_start, _ = shift_svc.shift_window(slot.date, slot.shift)
    return Schedule(
        start=now,
        qualifying_end=_local(day_before, settings.qualifying_close_time),
        premium_start=_local(day_before, settings.premium_round_start_time),
        end=slot_start - timedelta(minutes=settings.premium_close_before_slot_minutes),
    )


def current_round(a: Auction, now: datetime) -> AuctionRound | None:
    """The round implied by the clock (``None`` = not started yet)."""
    if a.status in (AuctionStatus.COMPLETED, AuctionStatus.CANCELLED):
        return AuctionRound.CLOSED
    if now < a.start_time:
        return None
    if now < a.qualifying_end_time:
        return AuctionRound.QUALIFYING
    if now < a.premium_start_time:
        return AuctionRound.BREAK
    if now < a.end_time:
        return AuctionRound.PREMIUM
    return AuctionRound.CLOSED


def round_ends_at(a: Auction, now: datetime) -> datetime | None:
    return {
        None: a.start_time,
        AuctionRound.QUALIFYING: a.qualifying_end_time,
        AuctionRound.BREAK: a.premium_start_time,
        AuctionRound.PREMIUM: a.end_time,
    }.get(current_round(a, now))


def _fmt_local(dt: datetime) -> str:
    return dt.astimezone(shift_svc.local_tz()).strftime("%H:%M on %d %b")


# --- seats --------------------------------------------------------------------


@dataclass
class SeatState:
    best: list[BestBid]
    confirmed: list[BestBid] | None  # None until the 12:00 threshold
    seats: list[Seat]


def load_best(db: Session, auction_id: int) -> list[BestBid]:
    rows = db.execute(select(Bid.advertiser_id, Bid.amount, Bid.round).where(Bid.auction_id == auction_id)).all()
    return seat_engine.best_bids([tuple(r) for r in rows])


def seat_state(db: Session, a: Auction, best: list[BestBid] | None = None) -> SeatState:
    best = best if best is not None else load_best(db, a.id)
    confirmed = (
        None
        if a.round == AuctionRound.QUALIFYING
        else [BestBid(c.advertiser_id, c.amount, "QUALIFYING") for c in a.confirmed_seats]
    )
    return SeatState(
        best, confirmed, seat_engine.seats(best, confirmed, settings.seats_per_slot, settings.confirmed_seats)
    )


def min_bid_for(a: Auction, state: SeatState, user_id: int | None, now: datetime) -> seat_engine.MinBid:
    """What ``user_id`` (or a newcomer, if None) must bid right now."""
    rnd = current_round(a, now)
    if rnd not in (AuctionRound.QUALIFYING, AuctionRound.PREMIUM):
        return seat_engine.MinBid(None, "Bidding is not open right now")
    return seat_engine.min_bid(
        user_id,
        state.best,
        state.confirmed,
        rnd == AuctionRound.PREMIUM,
        a.reserve_price,
        a.premium_floor,
        a.min_increment,
        settings.seats_per_slot,
    )


def seats_payload(seats: list[Seat]) -> list[dict]:
    return [
        {
            "seat": s.seat,
            "advertiser_id": s.advertiser_id,
            "alias": bidder_alias(s.advertiser_id) if s.advertiser_id else None,
            "amount": s.amount,
            "status": s.status,
        }
        for s in seats
    ]


# --- queries -----------------------------------------------------------------


def _auction_query():
    return select(Auction).options(
        selectinload(Auction.inventory_slot).selectinload(InventorySlot.pole).selectinload(Pole.road),
        selectinload(Auction.inventory_slot).selectinload(InventorySlot.pole).selectinload(Pole.owner),
        selectinload(Auction.winners),
        selectinload(Auction.confirmed_seats),
    )


def get_auction(db: Session, auction_id: int) -> Auction:
    auction = db.scalar(_auction_query().where(Auction.id == auction_id))
    if auction is None:
        raise NotFoundError(f"Auction {auction_id} not found")
    return auction


@dataclass
class AuctionFilters:
    status: AuctionStatus | None = None
    pole_id: int | None = None
    owner_id: int | None = None
    day: date | None = None
    shift: str | None = None
    bidder_id: int | None = None  # auctions this advertiser has bid on


def list_auctions(db: Session, f: AuctionFilters) -> list[Auction]:
    q = _auction_query().join(Auction.inventory_slot).join(InventorySlot.pole)
    if f.status is not None:
        q = q.where(Auction.status == f.status)
    if f.pole_id is not None:
        q = q.where(InventorySlot.pole_id == f.pole_id)
    if f.owner_id is not None:
        q = q.where(Pole.owner_id == f.owner_id)
    if f.day is not None:
        q = q.where(InventorySlot.date == f.day)
    if f.shift is not None:
        q = q.where(InventorySlot.shift == f.shift)
    if f.bidder_id is not None:
        q = q.where(Auction.id.in_(select(Bid.auction_id).where(Bid.advertiser_id == f.bidder_id)))
    return list(db.scalars(q.order_by(Auction.end_time.desc(), Auction.id)))


def bid_counts(db: Session, auction_ids: list[int]) -> dict[int, int]:
    if not auction_ids:
        return {}
    rows = db.execute(
        select(Bid.auction_id, func.count(Bid.id)).where(Bid.auction_id.in_(auction_ids)).group_by(Bid.auction_id)
    )
    return dict(rows.all())


def best_bids_for(db: Session, auction_ids: list[int]) -> dict[int, list[BestBid]]:
    """Best bid per advertiser for many auctions in one query."""
    if not auction_ids:
        return {}
    rows = db.execute(
        select(Bid.auction_id, Bid.advertiser_id, Bid.amount, Bid.round).where(Bid.auction_id.in_(auction_ids))
    ).all()
    grouped: dict[int, list[tuple[int, int, str]]] = {}
    for aid, adv, amount, rnd in rows:
        grouped.setdefault(aid, []).append((adv, amount, rnd))
    return {aid: seat_engine.best_bids(b) for aid, b in grouped.items()}


def list_bids(db: Session, auction_id: int) -> list[Bid]:
    get_auction(db, auction_id)
    return list(
        db.scalars(select(Bid).where(Bid.auction_id == auction_id).order_by(Bid.amount.desc(), Bid.timestamp))
    )


# --- lifecycle ---------------------------------------------------------------


def _started_event(a: Auction) -> AuctionEvent:
    return AuctionEvent(
        EventType.AUCTION_STARTED,
        a.id,
        {
            "start_time": a.start_time.isoformat(),
            "qualifying_end_time": a.qualifying_end_time.isoformat(),
            "premium_start_time": a.premium_start_time.isoformat(),
            "end_time": a.end_time.isoformat(),
            "reserve_price": a.reserve_price,
            "min_increment": a.min_increment,
        },
    )


def create_auction(
    db: Session,
    *,
    slot_id: int,
    start_time: datetime | None = None,
    qualifying_end_time: datetime | None = None,
    premium_start_time: datetime | None = None,
    end_time: datetime | None = None,
    reserve_price: int | None = None,
    min_increment: int | None = None,
    now: datetime | None = None,
) -> tuple[Auction, list[AuctionEvent]]:
    """Create a two-round auction for one inventory slot.

    Times default to the standard schedule (qualifying round until 12:00 the
    day before, premium 16:00 → 2h before the slot). Starts LIVE immediately
    when ``start_time`` is omitted or past, otherwise SCHEDULED.
    """
    now = now or utcnow()
    slot = db.get(InventorySlot, slot_id)
    if slot is None:
        raise NotFoundError(f"Inventory slot {slot_id} not found")
    if db.scalar(select(Auction.id).where(Auction.inventory_slot_id == slot_id)):
        raise ConflictError("This inventory slot already has an auction")
    if slot.status != SlotStatus.AVAILABLE:
        raise BusinessRuleError(f"Inventory slot is {slot.status.value}, not AVAILABLE")

    d = default_schedule(slot, now)
    start = ensure_utc(start_time) if start_time else now
    q_end = ensure_utc(qualifying_end_time) if qualifying_end_time else d.qualifying_end
    premium = ensure_utc(premium_start_time) if premium_start_time else d.premium_start
    end = ensure_utc(end_time) if end_time else d.end
    slot_start, _ = shift_svc.shift_window(slot.date, slot.shift)

    if q_end <= now:
        raise BusinessRuleError(
            f"The qualifying round for this slot closed at {_fmt_local(q_end)}; it can no longer be auctioned"
        )
    if not (start < q_end <= premium < end):
        raise BusinessRuleError("Schedule must satisfy: start < qualifying-round end ≤ premium start < end")
    if end > slot_start:
        raise BusinessRuleError("Auction must close before the advertised shift begins")

    reserve = reserve_price or slot.reserve_price
    auction = Auction(
        inventory_slot_id=slot.id,
        start_time=start,
        qualifying_end_time=q_end,
        premium_start_time=premium,
        end_time=end,
        reserve_price=reserve,
        min_increment=min_increment or default_min_increment(reserve),
        status=AuctionStatus.LIVE if start <= now else AuctionStatus.SCHEDULED,
        round=AuctionRound.QUALIFYING,
    )
    slot.status = SlotStatus.IN_AUCTION
    db.add(auction)
    db.commit()

    events = [_started_event(auction)] if auction.status == AuctionStatus.LIVE else []
    return get_auction(db, auction.id), events


def start_auction(db: Session, auction_id: int, now: datetime | None = None) -> list[AuctionEvent]:
    now = now or utcnow()
    auction = get_auction(db, auction_id)
    if auction.status != AuctionStatus.SCHEDULED:
        raise BusinessRuleError(f"Only scheduled auctions can be started (status: {auction.status.value})")
    if auction.qualifying_end_time <= now:
        raise BusinessRuleError("The qualifying round's closing time has already passed")
    auction.status = AuctionStatus.LIVE
    auction.round = AuctionRound.QUALIFYING
    auction.start_time = now
    db.commit()
    return [_started_event(auction)]


@dataclass
class BidResult:
    bid: Bid
    auction: Auction
    seats: list[Seat]
    bumped: list[int] = field(default_factory=list)
    events: list[AuctionEvent] = field(default_factory=list)


def _too_low_message(a: Auction, state: SeatState, user_id: int, required: int, premium: bool) -> str:
    holders = [s for s in state.seats if s.advertiser_id is not None and s.status != seat_engine.CONFIRMED]
    own = next((s for s in state.seats if s.advertiser_id == user_id), None)
    if own and own.status != seat_engine.CONFIRMED and not (premium and own.amount < (a.premium_floor or 0)):
        return (
            f"To raise your bid, bid at least ₹{required:,} "
            f"(at least ₹{a.min_increment:,} above your ₹{own.amount:,} and clear of other seats)"
        )
    if premium and required == a.premium_floor:
        top = state.best[0].amount if state.best else a.reserve_price
        return (
            f"Premium bids start at ₹{required:,} "
            f"({settings.premium_floor_multiplier:g}x the top qualifying bid of ₹{top:,})"
        )
    if holders and required > a.reserve_price:
        lowest = min(h.amount for h in holders)
        return (
            f"All open seats are taken. Bid at least ₹{required:,} to take the lowest seat "
            f"(₹{a.min_increment:,} above its ₹{lowest:,})"
        )
    return f"Bid must be at least the base price (reserve) of ₹{required:,}"


def place_bid(db: Session, auction_id: int, user: User, amount: int, now: datetime | None = None) -> BidResult:
    now = now or utcnow()
    if user.role != UserRole.ADVERTISER:
        raise PermissionDeniedError("Only advertisers can place bids")

    auction = get_auction(db, auction_id)
    rnd = current_round(auction, now)
    if auction.status in (AuctionStatus.COMPLETED, AuctionStatus.CANCELLED):
        raise BusinessRuleError("This auction has ended")
    if auction.status != AuctionStatus.LIVE or rnd is None:
        raise BusinessRuleError("This auction has not started yet")
    if rnd == AuctionRound.CLOSED:
        raise BusinessRuleError("This auction has expired")
    if rnd == AuctionRound.BREAK:
        raise BusinessRuleError(
            f"The qualifying round has closed. Premium bidding opens at {_fmt_local(auction.premium_start_time)}"
        )
    premium = rnd == AuctionRound.PREMIUM
    if premium and auction.round == AuctionRound.QUALIFYING:
        raise BusinessRuleError("Seats are being confirmed; try again in a moment")

    state = seat_state(db, auction)
    mb = min_bid_for(auction, state, user.id, now)
    if mb.amount is None:
        raise BusinessRuleError(mb.reason or "You can't bid right now")
    if amount < mb.amount:
        raise BusinessRuleError(_too_low_message(auction, state, user.id, mb.amount, premium))
    clash = seat_engine.clashes(
        amount, user.id, state.best, state.confirmed if premium else None, auction.min_increment, settings.seats_per_slot
    )
    if clash is not None:
        raise BusinessRuleError(
            f"Matching bids are not allowed: a seat already holds ₹{clash:,}. "
            f"Bid at least ₹{auction.min_increment:,} away from it"
        )

    # Optimistic concurrency: apply only if nobody else changed this auction
    # (or its round) since we validated.
    if premium:
        round_ok = and_(
            Auction.round.in_([AuctionRound.BREAK, AuctionRound.PREMIUM]),
            Auction.premium_start_time <= now,
            Auction.end_time > now,
        )
    else:
        round_ok = and_(Auction.round == AuctionRound.QUALIFYING, Auction.qualifying_end_time > now)
    new_top = amount > (auction.current_highest_bid or 0)
    values = {"version": Auction.version + 1}
    if new_top:
        values |= {"current_highest_bid": amount, "current_highest_bidder_id": user.id}
    result = db.execute(
        update(Auction)
        .where(
            Auction.id == auction.id,
            Auction.version == auction.version,
            Auction.status == AuctionStatus.LIVE,
            round_ok,
        )
        .values(**values)
        .execution_options(synchronize_session=False)
    )
    if result.rowcount != 1:
        db.rollback()
        raise ConflictError("Another bid was accepted first (or the round just changed). Check and try again.")

    bid = Bid(
        auction_id=auction.id,
        advertiser_id=user.id,
        amount=amount,
        round="PREMIUM" if premium else "QUALIFYING",
        timestamp=now,
    )
    db.add(bid)
    db.commit()
    db.refresh(auction)
    db.refresh(bid)

    after = seat_state(db, auction)
    holders_before = {s.advertiser_id for s in state.seats if s.advertiser_id}
    holders_after = {s.advertiser_id for s in after.seats if s.advertiser_id}
    bumped = sorted(holders_before - holders_after)
    newcomer_min = min_bid_for(auction, after, None, now).amount
    count = bid_counts(db, [auction.id]).get(auction.id, 0)

    events = [
        AuctionEvent(
            EventType.NEW_BID,
            auction.id,
            {
                "bid_id": bid.id,
                "amount": amount,
                "bidder_id": user.id,
                "bidder_alias": bidder_alias(user.id),
                "bid_count": count,
                "round": rnd.value,
                "seats": seats_payload(after.seats),
                "next_min_bid": newcomer_min,
            },
            timestamp=now,
        )
    ]
    for loser in bumped:
        events.append(
            AuctionEvent(
                EventType.OUTBID,
                auction.id,
                {"outbid_user_id": loser, "amount": amount, "next_min_bid": newcomer_min},
                timestamp=now,
            )
        )
    return BidResult(bid=bid, auction=auction, seats=after.seats, bumped=bumped, events=events)


def confirm_seats(db: Session, a: Auction, now: datetime) -> list[AuctionEvent]:
    """12:00 threshold: confirm the top qualifying bidders and set the premium
    floor. Does not commit."""
    best = load_best(db, a.id)
    for i, b in enumerate(best[: settings.confirmed_seats], start=1):
        a.confirmed_seats.append(ConfirmedSeat(auction_id=a.id, advertiser_id=b.advertiser_id, seat=i, amount=b.amount))
    a.premium_floor = seat_engine.premium_floor(
        best[0].amount if best else None,
        a.reserve_price,
        settings.premium_floor_multiplier,
        settings.auction_min_increment_inr,
    )
    a.round = AuctionRound.BREAK
    db.flush()
    state = seat_state(db, a, best)
    return [
        AuctionEvent(
            EventType.QUALIFYING_CLOSED,
            a.id,
            {
                "seats": seats_payload(state.seats),
                "confirmed_ids": [c.advertiser_id for c in a.confirmed_seats],
                "premium_floor": a.premium_floor,
                "premium_start_time": a.premium_start_time.isoformat(),
            },
            timestamp=now,
        )
    ]


def open_premium_round(a: Auction, now: datetime) -> AuctionEvent:
    a.round = AuctionRound.PREMIUM
    return AuctionEvent(
        EventType.PREMIUM_ROUND_STARTED,
        a.id,
        {"premium_floor": a.premium_floor, "end_time": a.end_time.isoformat()},
        timestamp=now,
    )


def _record_price_history(db: Session, auction: Auction, slot: InventorySlot, winners: list[Seat]) -> None:
    """Store the outcome for price trends (replaces any synthetic row).
    The price is the average winning seat price."""
    row = db.scalar(
        select(SlotPriceHistory).where(
            SlotPriceHistory.pole_id == slot.pole_id,
            SlotPriceHistory.date == slot.date,
            SlotPriceHistory.shift == slot.shift,
        )
    )
    if row is None:
        row = SlotPriceHistory(pole_id=slot.pole_id, date=slot.date, shift=slot.shift)
        db.add(row)
    row.base_price = auction.reserve_price
    row.clearing_price = round(sum(w.amount for w in winners) / len(winners)) if winners else None
    row.bid_count = db.scalar(select(func.count(Bid.id)).where(Bid.auction_id == auction.id)) or 0
    row.source = "auction"


def finalize_auction(db: Session, auction: Auction, now: datetime) -> AuctionEvent:
    """Close the auction: every seat holder wins and pays their own bid.
    Does not commit; callers own the transaction."""
    winners = [s for s in seat_state(db, auction).seats if s.advertiser_id is not None]
    auction.status = AuctionStatus.COMPLETED
    auction.round = AuctionRound.CLOSED
    auction.completed_at = now
    if auction.end_time > now:
        auction.end_time = now  # closed early by the auctioneer
    slot = auction.inventory_slot
    for w in winners:
        db.add(
            WinningAdvertisement(
                auction_id=auction.id, seat=w.seat, advertiser_id=w.advertiser_id, winning_bid=w.amount, created_at=now
            )
        )
    slot.status = SlotStatus.SOLD if winners else SlotStatus.UNSOLD
    _record_price_history(db, auction, slot, winners)
    return AuctionEvent(
        EventType.AUCTION_COMPLETED,
        auction.id,
        {
            "winners": [
                {"seat": w.seat, "advertiser_id": w.advertiser_id, "alias": bidder_alias(w.advertiser_id), "amount": w.amount}
                for w in winners
            ],
            "revenue": sum(w.amount for w in winners),
            "slot_status": slot.status.value,
        },
        timestamp=now,
    )


def complete_auction(db: Session, auction_id: int, now: datetime | None = None) -> list[AuctionEvent]:
    """Close an auction now, whatever its round (the auctioneer's "stop")."""
    now = now or utcnow()
    auction = get_auction(db, auction_id)
    if auction.status not in OPEN_STATUSES:
        raise BusinessRuleError(f"Auction is already {auction.status.value}")
    event = finalize_auction(db, auction, now)
    db.commit()
    return [event]


def advance_round(db: Session, auction_id: int, now: datetime | None = None) -> list[AuctionEvent]:
    """Move a live auction to its next round immediately (auctioneer / demo).

    QUALIFYING → BREAK (confirm seats now) → PREMIUM (open it now) → closed.
    """
    now = now or utcnow()
    a = get_auction(db, auction_id)
    if a.status != AuctionStatus.LIVE:
        raise BusinessRuleError(f"Only live auctions can be advanced (status: {a.status.value})")
    if a.round == AuctionRound.QUALIFYING:
        a.qualifying_end_time = now
        a.premium_start_time = max(a.premium_start_time, now)
        events = confirm_seats(db, a, now)
    elif a.round == AuctionRound.BREAK:
        a.premium_start_time = now
        events = [open_premium_round(a, now)]
    else:
        events = [finalize_auction(db, a, now)]
    a.version += 1
    db.commit()
    return events


def process_due(db: Session, now: datetime | None = None) -> list[AuctionEvent]:
    """Advance every auction whose next deadline has passed, in schedule order."""
    now = now or utcnow()
    events: list[AuctionEvent] = []

    def due(*where):
        return db.scalars(_auction_query().where(*where)).all()

    for a in due(Auction.status == AuctionStatus.SCHEDULED, Auction.start_time <= now):
        a.status, a.round = AuctionStatus.LIVE, AuctionRound.QUALIFYING
        events.append(_started_event(a))
    db.flush()

    for a in due(
        Auction.status == AuctionStatus.LIVE,
        Auction.round == AuctionRound.QUALIFYING,
        Auction.qualifying_end_time <= now,
    ):
        events += confirm_seats(db, a, now)
        a.version += 1
    db.flush()

    for a in due(
        Auction.status == AuctionStatus.LIVE,
        Auction.round == AuctionRound.BREAK,
        Auction.premium_start_time <= now,
        Auction.end_time > now,
    ):
        events.append(open_premium_round(a, now))
    db.flush()

    for a in due(Auction.status == AuctionStatus.LIVE, Auction.end_time <= now):
        events.append(finalize_auction(db, a, now))

    if events:
        db.commit()
    return events

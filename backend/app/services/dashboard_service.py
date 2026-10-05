"""Read models for the advertiser dashboard and the admin's pole analysis."""

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.core.exceptions import NotFoundError
from app.models import (
    Auction,
    AuctionRound,
    AuctionStatus,
    Bid,
    FootfallCategory,
    InventorySlot,
    Pole,
    SlotPriceHistory,
    User,
    WinningAdvertisement,
)
from app.schemas.dashboard import (
    AdvertiserDashboard,
    AdvertiserKpis,
    AuctionRow,
    BidHistoryPage,
    BidHistoryRow,
    PoleAnalysis,
    PoleAnalysisKpis,
    RevenuePoint,
    SlotPerformance,
    WonSeat,
)
from app.services import auction_service, inventory_service, seat_engine, slot_footfall_service
from app.services import shifts as shift_svc
from app.utils.geo import haversine_km
from app.utils.time import utcnow

REVENUE_DAYS = 14


def _auction_query():
    return select(Auction).options(
        selectinload(Auction.inventory_slot).selectinload(InventorySlot.pole),
        selectinload(Auction.confirmed_seats),
        selectinload(Auction.winners),
    )


def auction_rows(db: Session, auctions: list[Auction], viewer: User | None = None) -> list[AuctionRow]:
    """Dashboard rows, computing seats in bulk. ``viewer`` adds 'my' columns."""
    if not auctions:
        return []
    now = utcnow()
    ids = [a.id for a in auctions]
    best = auction_service.best_bids_for(db, ids)
    counts = auction_service.bid_counts(db, ids)
    profiles = slot_footfall_service.load_profiles(db, list({a.inventory_slot.pole_id for a in auctions}))
    rows = []
    for a in auctions:
        slot, pole = a.inventory_slot, a.inventory_slot.pole
        state = auction_service.seat_state(db, a, best.get(a.id, []))
        completed = a.status == AuctionStatus.COMPLETED
        filled = len(a.winners) if completed else sum(1 for s in state.seats if s.advertiser_id)
        row = AuctionRow(
            id=a.id,
            pole_code=pole.code,
            pole_name=pole.name,
            category=pole.category,
            date=slot.date,
            shift=slot.shift,
            shift_label=shift_svc.get_shift(slot.shift).label,
            status=a.status,
            round=auction_service.current_round(a, now),
            round_ends_at=auction_service.round_ends_at(a, now),
            base_price=a.reserve_price,
            top_bid=a.current_highest_bid,
            next_min_bid=None if completed else auction_service.min_bid_for(a, state, None, now).amount,
            seats_filled=filled,
            seats_total=settings.seats_per_slot,
            bid_count=counts.get(a.id, 0),
            slot_footfall=slot_footfall_service.shift_footfall(profiles.get(pole.id), slot.date, slot.shift),
            revenue=sum(w.winning_bid for w in a.winners) if completed else 0,
        )
        if viewer is not None:
            mine = next((b for b in state.best if b.advertiser_id == viewer.id), None)
            seat = next((s for s in state.seats if s.advertiser_id == viewer.id), None)
            won = next((w for w in a.winners if w.advertiser_id == viewer.id), None)
            row.my_bid = mine.amount if mine else None
            row.my_seat = won.seat if won else seat.seat if seat else None
            row.my_seat_status = "WON" if won else seat.status if seat else None
            row.my_min_bid = None if completed else auction_service.min_bid_for(a, state, viewer.id, now).amount
        rows.append(row)
    return rows


def _revenue_by_day(db: Session, pole_ids: list[int] | None, days: int = REVENUE_DAYS) -> list[RevenuePoint]:
    """Booked revenue per advertising date for the last ``days`` days (incl. tomorrow)."""
    end = shift_svc.local_today() + timedelta(days=1)
    start = end - timedelta(days=days - 1)
    q = (
        select(InventorySlot.date, func.sum(WinningAdvertisement.winning_bid), func.count(WinningAdvertisement.id))
        .join(Auction, WinningAdvertisement.auction_id == Auction.id)
        .join(InventorySlot, Auction.inventory_slot_id == InventorySlot.id)
        .where(InventorySlot.date >= start, InventorySlot.date <= end)
        .group_by(InventorySlot.date)
    )
    if pole_ids is not None:
        q = q.where(InventorySlot.pole_id.in_(pole_ids))
    totals = {d: (int(r), int(n)) for d, r, n in db.execute(q).all()}
    return [
        RevenuePoint(date=d, revenue=totals.get(d, (0, 0))[0], seats=totals.get(d, (0, 0))[1])
        for d in (start + timedelta(days=i) for i in range(days))
    ]


# --- pole analysis ----------------------------------------------------------------

ANALYSIS_REVENUE_DAYS = 30


def pole_analysis(db: Session, code: str) -> PoleAnalysis:
    """Status, footfall, pricing and sales performance of one pole."""
    pole = db.scalar(select(Pole).options(selectinload(Pole.road)).where(Pole.code == code.upper()))
    if pole is None:
        raise NotFoundError(f"Pole {code} not found")

    tomorrow = shift_svc.tomorrow()
    week = [tomorrow + timedelta(days=i) for i in range(7)]
    profile = slot_footfall_service.load_profiles(db, [pole.id]).get(pole.id)

    window_start = shift_svc.local_today() - timedelta(days=settings.price_trend_days)
    history = defaultdict(list)
    for h in db.scalars(
        select(SlotPriceHistory).where(SlotPriceHistory.pole_id == pole.id, SlotPriceHistory.date >= window_start)
    ):
        history[h.shift].append(h)

    slots = []
    for shift in shift_svc.list_shifts():
        days = history.get(shift.code, [])
        sold = [h.clearing_price for h in days if h.clearing_price is not None]
        footfalls = [slot_footfall_service.shift_footfall(profile, d, shift.code) or 0 for d in week]
        slots.append(
            SlotPerformance(
                shift=shift.code,
                label=shift.label,
                avg_footfall=round(sum(footfalls) / len(footfalls)),
                base_price=inventory_service.quote_slot(pole, tomorrow, shift.code, profile).reserve_price,
                avg_price=round(sum(sold) / len(sold)) if sold else None,
                sell_through=round(len(sold) / len(days), 3) if days else 0.0,
            )
        )

    all_days = [h for hs in history.values() for h in hs]
    sold_days = [h for h in all_days if h.clearing_price is not None]
    revenue_total, seats_sold = db.execute(
        select(func.coalesce(func.sum(WinningAdvertisement.winning_bid), 0), func.count(WinningAdvertisement.id))
        .join(Auction, WinningAdvertisement.auction_id == Auction.id)
        .join(InventorySlot, Auction.inventory_slot_id == InventorySlot.id)
        .where(InventorySlot.pole_id == pole.id)
    ).one()
    revenue = _revenue_by_day(db, [pole.id], ANALYSIS_REVENUE_DAYS)
    open_slots = db.scalar(
        select(func.count(Auction.id))
        .join(InventorySlot, Auction.inventory_slot_id == InventorySlot.id)
        .where(
            InventorySlot.pole_id == pole.id,
            InventorySlot.date.between(week[0], week[-1]),
            Auction.status.in_([AuctionStatus.SCHEDULED, AuctionStatus.LIVE]),
        )
    )
    return PoleAnalysis(
        code=pole.code,
        name=pole.name,
        road_name=pole.road.name if pole.road else None,
        category=pole.category,
        status=pole.status,
        footfall=pole.footfall,
        footfall_score=pole.footfall_score,
        visibility_score=pole.visibility_score,
        open_slots=open_slots or 0,
        window_days=settings.price_trend_days,
        kpis=PoleAnalysisKpis(
            revenue_total=revenue_total,
            revenue_30d=sum(p.revenue for p in revenue),
            seats_sold=seats_sold,
            avg_seat_price=round(revenue_total / seats_sold) if seats_sold else None,
            sell_through=round(len(sold_days) / len(all_days), 3) if all_days else 0.0,
            price_vs_base=(
                round(sum(h.clearing_price for h in sold_days) / sum(h.base_price for h in sold_days), 2)
                if sold_days
                else None
            ),
        ),
        revenue_by_day=revenue,
        slots=slots,
    )


# --- advertiser -----------------------------------------------------------------


MY_AUCTIONS_LIMIT = 50


def advertiser_dashboard(db: Session, user: User) -> AdvertiserDashboard:
    bid_on = select(Bid.auction_id).where(Bid.advertiser_id == user.id).distinct()
    now = utcnow()
    live = list(db.scalars(_auction_query().where(Auction.id.in_(bid_on), Auction.status == AuctionStatus.LIVE)))
    rows = auction_rows(db, live, viewer=user)
    # Most urgent first: soonest round deadline (rows without one last).
    rows.sort(key=lambda r: (r.round_ends_at is None, r.round_ends_at or now))

    won_rows = db.execute(
        select(WinningAdvertisement, InventorySlot, Pole)
        .join(Auction, WinningAdvertisement.auction_id == Auction.id)
        .join(InventorySlot, Auction.inventory_slot_id == InventorySlot.id)
        .join(Pole, InventorySlot.pole_id == Pole.id)
        .where(WinningAdvertisement.advertiser_id == user.id)
        .order_by(InventorySlot.date.desc())
    ).all()
    profiles = slot_footfall_service.load_profiles(db, list({p.id for _, _, p in won_rows}))
    won = [
        WonSeat(
            auction_id=w.auction_id,
            pole_code=p.code,
            date=s.date,
            shift_label=shift_svc.get_shift(s.shift).label,
            seat=w.seat,
            amount=w.winning_bid,
            slot_footfall=slot_footfall_service.shift_footfall(profiles.get(p.id), s.date, s.shift),
            day_footfall=(
                slot_footfall_service.day_total(profiles[p.id], s.date.weekday()) if p.id in profiles else p.footfall
            ),
        )
        for w, s, p in won_rows
    ]
    open_now = db.scalar(
        select(func.count(Auction.id)).where(
            Auction.status == AuctionStatus.LIVE,
            Auction.round.in_([AuctionRound.QUALIFYING, AuctionRound.PREMIUM]),
        )
    )
    held = [r for r in rows if r.my_seat]
    return AdvertiserDashboard(
        kpis=AdvertiserKpis(
            seats_held=len(held),
            seats_at_risk=sum(1 for r in held if r.my_seat_status != seat_engine.CONFIRMED),
            seats_won=len(won),
            total_spend=sum(w.amount for w in won),
            open_auctions=open_now or 0,
        ),
        my_auctions=rows[:MY_AUCTIONS_LIMIT],
        my_auctions_total=len(rows),
        won=won,
    )



def bid_history(db: Session, user: User, limit: int = 50, offset: int = 0) -> BidHistoryPage:
    """Every bid ``user`` has placed, newest first, with its outcome."""
    total = db.scalar(select(func.count(Bid.id)).where(Bid.advertiser_id == user.id)) or 0
    bids = list(
        db.scalars(
            select(Bid)
            .where(Bid.advertiser_id == user.id)
            .order_by(Bid.timestamp.desc(), Bid.id.desc())
            .offset(offset)
            .limit(limit)
        )
    )
    ids = list({b.auction_id for b in bids})
    auctions = {a.id: a for a in db.scalars(_auction_query().where(Auction.id.in_(ids)))} if ids else {}
    # The user's highest bid per auction: only that one can hold or win a seat.
    my_best = dict(
        db.execute(
            select(Bid.auction_id, func.max(Bid.amount))
            .where(Bid.advertiser_id == user.id, Bid.auction_id.in_(ids))
            .group_by(Bid.auction_id)
        ).all()
    ) if ids else {}
    live_ids = [aid for aid, a in auctions.items() if a.status in auction_service.OPEN_STATUSES]
    best = auction_service.best_bids_for(db, live_ids)
    my_seat: dict[int, int | None] = {}
    for aid in live_ids:
        state = auction_service.seat_state(db, auctions[aid], best.get(aid, []))
        my_seat[aid] = next((s.seat for s in state.seats if s.advertiser_id == user.id), None)

    items = []
    for b in bids:
        a = auctions[b.auction_id]
        slot = a.inventory_slot
        seat = None
        if b.amount < my_best[a.id]:
            outcome = "RAISED"
        elif a.status == AuctionStatus.COMPLETED:
            won = next((w for w in a.winners if w.advertiser_id == user.id), None)
            outcome, seat = ("WON", won.seat) if won else ("LOST", None)
        elif a.status == AuctionStatus.CANCELLED:
            outcome = "CANCELLED"
        else:
            seat = my_seat.get(a.id)
            outcome = "HOLDING" if seat else "OUTBID"
        items.append(
            BidHistoryRow(
                bid_id=b.id,
                placed_at=b.timestamp,
                auction_id=a.id,
                pole_code=slot.pole.code,
                category=slot.pole.category,
                date=slot.date,
                shift_label=shift_svc.get_shift(slot.shift).label,
                amount=b.amount,
                round=b.round,
                outcome=outcome,
                seat=seat,
            )
        )
    return BidHistoryPage(items=items, total=total)

@dataclass
class OpportunityFilters:
    day: date | None = None
    shift: str | None = None
    category: FootfallCategory | None = None
    min_footfall: int | None = None  # slot footfall
    min_score: int | None = None  # pole footfall score
    max_price: int | None = None  # current minimum bid
    round: AuctionRound | None = None
    latitude: float | None = None
    longitude: float | None = None
    radius_km: float | None = None
    limit: int = 60


def opportunities(db: Session, f: OpportunityFilters, viewer: User | None) -> list[AuctionRow]:
    """Live auctions matching the filters, busiest slots first."""
    q = (
        select(Auction, InventorySlot, Pole)
        .join(InventorySlot, Auction.inventory_slot_id == InventorySlot.id)
        .join(Pole, InventorySlot.pole_id == Pole.id)
        .where(Auction.status == AuctionStatus.LIVE)
    )
    if f.day:
        q = q.where(InventorySlot.date == f.day)
    if f.shift:
        q = q.where(InventorySlot.shift == f.shift)
    if f.category:
        q = q.where(Pole.category == f.category)
    if f.min_score is not None:
        q = q.where(Pole.footfall_score >= f.min_score)
    candidates = db.execute(q).all()

    now = utcnow()
    profiles = slot_footfall_service.load_profiles(db, list({p.id for _, _, p in candidates}))
    scored = []
    for a, s, p in candidates:
        if f.round and auction_service.current_round(a, now) != f.round:
            continue
        if f.radius_km and f.latitude is not None and f.longitude is not None:
            if haversine_km(f.latitude, f.longitude, p.latitude, p.longitude) > f.radius_km:
                continue
        sf = slot_footfall_service.shift_footfall(profiles.get(p.id), s.date, s.shift) or 0
        if f.min_footfall is not None and sf < f.min_footfall:
            continue
        scored.append((sf, a))
    scored.sort(key=lambda x: -x[0])

    # Price depends on seats, so filter by price after computing the top slice.
    ids = [a.id for _, a in scored[: f.limit * 4]]
    auctions = list(db.scalars(_auction_query().where(Auction.id.in_(ids)))) if ids else []
    order = {aid: i for i, aid in enumerate(ids)}
    auctions.sort(key=lambda a: order[a.id])
    rows = auction_rows(db, auctions, viewer)
    if f.max_price is not None:
        rows = [r for r in rows if r.next_min_bid is not None and r.next_min_bid <= f.max_price]
    return rows[: f.limit]

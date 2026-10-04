"""Build API representations of auctions and bids."""

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import Auction, AuctionStatus, Bid, User, UserRole
from app.schemas.auction import (
    AuctionBrief,
    AuctionOut,
    AuctionPole,
    BidOut,
    ExpectedPriceOut,
    SeatOut,
    ViewerOut,
    WinnerOut,
)
from app.services import price_trend_service, seat_engine, slot_footfall_service, tariff_service
from app.services import shifts as shift_svc
from app.services.auction_service import (
    SeatState,
    best_bids_for,
    bid_counts,
    bidder_alias,
    current_round,
    min_bid_for,
    round_ends_at,
    seat_state,
)
from app.utils.time import utcnow


def expected_out(e: price_trend_service.ExpectedPrice | None) -> ExpectedPriceOut | None:
    if e is None:
        return None
    return ExpectedPriceOut(
        weekday=e.weekday_label,
        average=e.average,
        low=e.low,
        high=e.high,
        min_price=e.min_price,
        max_price=e.max_price,
        samples=e.samples,
        days=e.days,
    )


def seats_out(seats: list[seat_engine.Seat]) -> list[SeatOut]:
    return [
        SeatOut(
            seat=s.seat,
            advertiser_id=s.advertiser_id,
            alias=bidder_alias(s.advertiser_id) if s.advertiser_id else None,
            amount=s.amount,
            status=s.status,
        )
        for s in seats
    ]


def viewer_out(auction: Auction, state: SeatState, user: User | None) -> ViewerOut | None:
    if user is None:
        return None
    seat = next((s for s in state.seats if s.advertiser_id == user.id), None)
    if user.role != UserRole.ADVERTISER:
        mb = seat_engine.MinBid(None, "Only advertiser accounts can bid")
    else:
        mb = min_bid_for(auction, state, user.id, utcnow())
    return ViewerOut(
        seat=seat.seat if seat else None,
        seat_status=seat.status if seat else None,
        next_min_bid=mb.amount,
        can_bid=mb.amount is not None,
        reason=mb.reason,
    )


def to_auction_out(
    auction: Auction,
    state: SeatState,
    bid_count: int,
    expected: ExpectedPriceOut | None = None,
    slot_footfall: int | None = None,
    user: User | None = None,
) -> AuctionOut:
    slot = auction.inventory_slot
    pole = slot.pole
    shift = shift_svc.get_shift(slot.shift)
    shift_start, shift_end = shift_svc.shift_window(slot.date, slot.shift)
    now = utcnow()
    if auction.status == AuctionStatus.COMPLETED:
        winners = [
            WinnerOut(seat=w.seat, advertiser_id=w.advertiser_id, alias=bidder_alias(w.advertiser_id), amount=w.winning_bid)
            for w in auction.winners
        ]
        seats = [
            SeatOut(seat=w.seat, advertiser_id=w.advertiser_id, alias=w.alias, amount=w.amount, status="WON")
            for w in winners
        ]
        seats += [
            SeatOut(seat=i, advertiser_id=None, alias=None, amount=None, status=seat_engine.OPEN)
            for i in range(len(seats) + 1, settings.seats_per_slot + 1)
        ]
    else:
        winners, seats = [], seats_out(state.seats)
    return AuctionOut(
        id=auction.id,
        status=auction.status,
        round=current_round(auction, now),
        round_ends_at=round_ends_at(auction, now),
        pole=AuctionPole(
            id=pole.id,
            code=pole.code,
            name=pole.name,
            road_name=pole.road.name if pole.road else None,
            latitude=pole.latitude,
            longitude=pole.longitude,
            footfall=pole.footfall,
            footfall_score=pole.footfall_score,
            visibility_score=pole.visibility_score,
            category=pole.category,
        ),
        inventory_slot_id=slot.id,
        slot_status=slot.status,
        date=slot.date,
        shift=slot.shift,
        shift_label=shift.label,
        demand=tariff_service.slot_demand(slot_footfall, pole.footfall, slot.shift),
        shift_start=shift_start,
        shift_end=shift_end,
        start_time=auction.start_time,
        qualifying_end_time=auction.qualifying_end_time,
        premium_start_time=auction.premium_start_time,
        end_time=auction.end_time,
        seats=seats,
        seats_total=settings.seats_per_slot,
        confirmed_seats=settings.confirmed_seats,
        premium_floor=auction.premium_floor,
        reserve_price=auction.reserve_price,
        min_increment=auction.min_increment,
        current_highest_bid=auction.current_highest_bid,
        next_min_bid=min_bid_for(auction, state, None, now).amount,
        bid_count=bid_count,
        completed_at=auction.completed_at,
        winners=winners,
        revenue=sum(w.amount for w in winners),
        viewer=viewer_out(auction, state, user),
        expected_price=expected,
        slot_footfall=slot_footfall,
        server_time=now,
    )


def auctions_out(db: Session, auctions: list[Auction], user: User | None = None) -> list[AuctionOut]:
    ids = [a.id for a in auctions]
    counts = bid_counts(db, ids)
    best = best_bids_for(db, ids)
    pole_ids = list({a.inventory_slot.pole_id for a in auctions})
    table = price_trend_service.expected_prices(db, pole_ids)
    profiles = slot_footfall_service.load_profiles(db, pole_ids)
    out = []
    for a in auctions:
        s = a.inventory_slot
        out.append(
            to_auction_out(
                a,
                seat_state(db, a, best.get(a.id, [])),
                counts.get(a.id, 0),
                expected_out(price_trend_service.expected_for(table, s.pole_id, s.shift, s.date)),
                slot_footfall_service.shift_footfall(profiles.get(s.pole_id), s.date, s.shift),
                user,
            )
        )
    return out


def auction_out(db: Session, auction: Auction, user: User | None = None) -> AuctionOut:
    return auctions_out(db, [auction], user)[0]


def to_bid_out(bid: Bid) -> BidOut:
    return BidOut(
        id=bid.id,
        auction_id=bid.auction_id,
        advertiser_id=bid.advertiser_id,
        bidder_alias=bidder_alias(bid.advertiser_id),
        amount=bid.amount,
        round=bid.round,
        timestamp=bid.timestamp,
    )


def auction_brief(auction: Auction, bid_count: int, state: SeatState) -> AuctionBrief:
    now = utcnow()
    return AuctionBrief(
        id=auction.id,
        status=auction.status,
        round=current_round(auction, now),
        round_ends_at=round_ends_at(auction, now),
        end_time=auction.end_time,
        current_highest_bid=auction.current_highest_bid,
        bid_count=bid_count,
        next_min_bid=min_bid_for(auction, state, None, now).amount,
        premium_floor=auction.premium_floor,
        seats=seats_out(state.seats),
    )

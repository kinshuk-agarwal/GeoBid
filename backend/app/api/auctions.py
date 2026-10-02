from datetime import date

from fastapi import APIRouter, status

from app.api.deps import AdminUser, AdvertiserUser, DbSession, OptionalUser
from app.models import AuctionStatus
from app.schemas.auction import AuctionCreate, AuctionOut, BidCreate, BidOut, BidPlaced
from app.services import auction_service
from app.services.auction_service import AuctionFilters
from app.services.auction_views import auction_out, auctions_out, to_bid_out
from app.services.events import event_bus

router = APIRouter(prefix="/auctions", tags=["auctions"])


@router.get("", response_model=list[AuctionOut])
def list_auctions(
    db: DbSession,
    status: AuctionStatus | None = None,
    pole_id: int | None = None,
    date: date | None = None,
    shift: str | None = None,
) -> list[AuctionOut]:
    filters = AuctionFilters(status=status, pole_id=pole_id, day=date, shift=shift)
    return auctions_out(db, auction_service.list_auctions(db, filters))


@router.get("/{auction_id}", response_model=AuctionOut)
def get_auction(auction_id: int, db: DbSession, user: OptionalUser) -> AuctionOut:
    """Includes ``viewer`` (your seat and minimum bid) when signed in."""
    return auction_out(db, auction_service.get_auction(db, auction_id), user)


@router.post("", response_model=AuctionOut, status_code=status.HTTP_201_CREATED)
def create_auction(body: AuctionCreate, db: DbSession, _admin: AdminUser) -> AuctionOut:
    auction, events = auction_service.create_auction(
        db,
        slot_id=body.inventory_slot_id,
        start_time=body.start_time,
        qualifying_end_time=body.qualifying_end_time,
        premium_start_time=body.premium_start_time,
        end_time=body.end_time,
        reserve_price=body.reserve_price,
        min_increment=body.min_increment,
    )
    event_bus.publish(events)
    return auction_out(db, auction)


@router.post("/{auction_id}/start", response_model=AuctionOut)
def start_auction(auction_id: int, db: DbSession, _admin: AdminUser) -> AuctionOut:
    event_bus.publish(auction_service.start_auction(db, auction_id))
    return auction_out(db, auction_service.get_auction(db, auction_id))


@router.post("/{auction_id}/advance", response_model=AuctionOut)
def advance_round(auction_id: int, db: DbSession, _admin: AdminUser) -> AuctionOut:
    """Move to the next round now: QUALIFYING → BREAK (seats 1-2 confirmed)
    → PREMIUM → completed. Lets an auctioneer or a demo skip the waiting."""
    event_bus.publish(auction_service.advance_round(db, auction_id))
    return auction_out(db, auction_service.get_auction(db, auction_id))


@router.post("/{auction_id}/complete", response_model=AuctionOut)
def complete_auction(auction_id: int, db: DbSession, _admin: AdminUser) -> AuctionOut:
    """Stop the auction now: bidding closes and the highest bid wins."""
    event_bus.publish(auction_service.complete_auction(db, auction_id))
    return auction_out(db, auction_service.get_auction(db, auction_id))


@router.get("/{auction_id}/bids", response_model=list[BidOut])
def list_bids(auction_id: int, db: DbSession) -> list[BidOut]:
    return [to_bid_out(b) for b in auction_service.list_bids(db, auction_id)]


@router.post("/{auction_id}/bids", response_model=BidPlaced, status_code=status.HTTP_201_CREATED)
def place_bid(auction_id: int, body: BidCreate, db: DbSession, user: AdvertiserUser) -> BidPlaced:
    result = auction_service.place_bid(db, auction_id, user, body.amount)
    event_bus.publish(result.events)
    return BidPlaced(bid=to_bid_out(result.bid), auction=auction_out(db, result.auction, user))

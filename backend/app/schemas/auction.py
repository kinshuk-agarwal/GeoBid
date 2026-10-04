from datetime import date, datetime

from pydantic import BaseModel, Field

from app.models.enums import AuctionRound, AuctionStatus, FootfallCategory, SlotStatus


class SeatOut(BaseModel):
    """One of the slot's rotating ad seats."""

    seat: int  # 1-based
    advertiser_id: int | None
    alias: str | None
    amount: int | None
    # LEADING (top 2 in the qualifying round) · CONFIRMED (secured at 12:00)
    # · PROVISIONAL (qualifying bid; can be bumped) · PREMIUM (premium bid;
    # can be bumped by a higher one) · OPEN (empty)
    status: str


class AuctionBrief(BaseModel):
    """Compact auction state embedded in inventory slots."""

    id: int
    status: AuctionStatus
    round: AuctionRound | None
    round_ends_at: datetime | None
    end_time: datetime
    current_highest_bid: int | None
    bid_count: int
    next_min_bid: int | None  # what a newcomer must bid now (null = no bidding now)
    premium_floor: int | None = None
    seats: list[SeatOut] = []


class ExpectedPriceOut(BaseModel):
    """What this pole-shift has typically sold for on this weekday."""

    weekday: str  # "Sat"
    average: int
    low: int  # rounded range, e.g. 9,000-10,000
    high: int
    min_price: int
    max_price: int
    samples: int  # days with a sale in the look-back window
    days: int


class AuctionPole(BaseModel):
    id: int
    code: str
    name: str
    road_name: str | None
    latitude: float
    longitude: float
    footfall: int
    footfall_score: int
    visibility_score: int
    category: FootfallCategory


class WinnerOut(BaseModel):
    seat: int
    advertiser_id: int
    alias: str
    amount: int


class ViewerOut(BaseModel):
    """The signed-in user's position in this auction."""

    seat: int | None
    seat_status: str | None
    next_min_bid: int | None
    can_bid: bool
    reason: str | None  # why not, when can_bid is false


class AuctionOut(BaseModel):
    id: int
    status: AuctionStatus
    # Round implied by the clock (null = not started). Bidding happens in
    # QUALIFYING (anyone) and PREMIUM (anyone except confirmed holders).
    round: AuctionRound | None
    round_ends_at: datetime | None
    pole: AuctionPole
    inventory_slot_id: int
    slot_status: SlotStatus
    date: date
    shift: str
    shift_label: str
    demand: str
    shift_start: datetime
    shift_end: datetime
    start_time: datetime
    qualifying_end_time: datetime
    premium_start_time: datetime
    end_time: datetime
    seats: list[SeatOut]
    seats_total: int
    confirmed_seats: int  # how many top seats are confirmed at 12:00
    # Premium-round starting price (1.5x top qualifying bid); null before 12:00.
    premium_floor: int | None
    reserve_price: int
    min_increment: int
    current_highest_bid: int | None
    next_min_bid: int | None  # for a newcomer
    bid_count: int
    completed_at: datetime | None
    winners: list[WinnerOut]
    revenue: int
    viewer: ViewerOut | None = None
    expected_price: ExpectedPriceOut | None = None
    slot_footfall: int | None = None
    # Lets clients correct their countdown for clock skew.
    server_time: datetime


class BidOut(BaseModel):
    id: int
    auction_id: int
    advertiser_id: int
    bidder_alias: str
    amount: int
    round: str
    timestamp: datetime


class BidCreate(BaseModel):
    amount: int = Field(gt=0, description="Bid amount in INR")


class BidPlaced(BaseModel):
    bid: BidOut
    auction: AuctionOut


class AuctionCreate(BaseModel):
    """Times default to the standard schedule: qualifying round until 12:00 on
    the day before the ad date, premium round 16:00 → 2 hours before the slot."""

    inventory_slot_id: int
    start_time: datetime | None = Field(default=None, description="Omit to start immediately")
    qualifying_end_time: datetime | None = None
    premium_start_time: datetime | None = None
    end_time: datetime | None = None
    reserve_price: int | None = Field(default=None, gt=0, description="Override the base price")
    min_increment: int | None = Field(default=None, gt=0)

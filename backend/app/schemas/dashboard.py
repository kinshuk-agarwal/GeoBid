from datetime import date, datetime

from pydantic import BaseModel

from app.models.enums import AuctionRound, AuctionStatus, FootfallCategory, PoleStatus


class AuctionRow(BaseModel):
    """One auction (pole + date + slot) in a dashboard table."""

    id: int
    pole_code: str
    pole_name: str
    category: FootfallCategory
    date: date
    shift: str
    shift_label: str
    status: AuctionStatus
    round: AuctionRound | None
    round_ends_at: datetime | None
    base_price: int
    top_bid: int | None
    next_min_bid: int | None  # for a newcomer
    seats_filled: int
    seats_total: int
    bid_count: int
    slot_footfall: int | None
    revenue: int  # completed auctions: sum of seat prices
    # advertiser view only
    my_bid: int | None = None
    my_seat: int | None = None
    my_seat_status: str | None = None
    my_min_bid: int | None = None


class RevenuePoint(BaseModel):
    date: date
    revenue: int
    seats: int


class SlotPerformance(BaseModel):
    shift: str
    label: str
    avg_footfall: int  # average over the 7 weekdays
    base_price: int  # tomorrow's base price
    avg_price: int | None  # average selling price over the trend window
    sell_through: float  # share of days the slot sold (0-1)


class PoleAnalysisKpis(BaseModel):
    revenue_total: int
    revenue_30d: int
    seats_sold: int
    avg_seat_price: int | None
    sell_through: float  # all slots, trend window
    price_vs_base: float | None  # average selling price / base price


class PoleAnalysis(BaseModel):
    """Performance and status of one pole, for the admin."""

    code: str
    name: str
    road_name: str | None
    category: FootfallCategory
    status: PoleStatus
    footfall: int
    footfall_score: int
    visibility_score: int
    open_slots: int  # slots on sale over the next 7 days
    window_days: int
    kpis: PoleAnalysisKpis
    revenue_by_day: list[RevenuePoint]
    slots: list[SlotPerformance]


class AdvertiserKpis(BaseModel):
    seats_held: int  # live auctions where you hold a seat
    seats_at_risk: int  # held seats that can still be taken
    seats_won: int
    total_spend: int
    open_auctions: int  # live auctions accepting bids now


class WonSeat(BaseModel):
    auction_id: int
    pole_code: str
    date: date
    shift_label: str
    seat: int
    amount: int


class AdvertiserDashboard(BaseModel):
    kpis: AdvertiserKpis
    my_auctions: list[AuctionRow]  # the most urgent (soonest round deadline) first
    my_auctions_total: int
    won: list[WonSeat]


class BidHistoryRow(BaseModel):
    """One bid an advertiser placed, with what became of it."""

    bid_id: int
    placed_at: datetime
    auction_id: int
    pole_code: str
    category: FootfallCategory
    date: date
    shift_label: str
    amount: int
    round: str  # QUALIFYING | PREMIUM
    # WON · HOLDING (seat held, auction live) · OUTBID · RAISED (you bid higher
    # later in the same auction) · LOST · CANCELLED
    outcome: str
    seat: int | None


class BidHistoryPage(BaseModel):
    items: list[BidHistoryRow]
    total: int

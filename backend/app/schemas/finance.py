from datetime import date

from pydantic import BaseModel

from app.models.enums import FootfallCategory


class PeriodTotal(BaseModel):
    """Revenue over a period and the same-length period before it."""

    revenue: int
    seats: int
    previous_revenue: int


class FinanceKpis(BaseModel):
    today: PeriodTotal
    last_7_days: PeriodTotal
    last_30_days: PeriodTotal
    all_time_revenue: int
    all_time_seats: int
    # Over the selected window:
    avg_seat_price: int | None
    seat_fill_rate: float  # seats sold / seats offered in completed auctions
    premium_share: float  # share of revenue from seats won in the premium round
    active_buyers: int
    repeat_buyer_rate: float  # buyers with purchases on 2+ days / active buyers


class RevenueBucket(BaseModel):
    start: date  # first day of the day / week (Monday) / month
    qualifying: int  # revenue from seats won in the qualifying round
    premium: int  # revenue from seats won in the premium round
    seats: int


class AdvertiserFinance(BaseModel):
    advertiser_id: int
    name: str
    revenue: int
    seats: int
    avg_price: int
    share: float  # of window revenue
    purchase_days: int  # distinct advertising days bought
    auctions_bid: int  # completed auctions in the window they bid on
    win_rate: float  # auctions won / auctions bid
    first_purchase: date
    last_purchase: date


class PoleFinance(BaseModel):
    code: str
    name: str
    road_name: str | None
    category: FootfallCategory
    revenue: int
    seats: int
    avg_price: int
    share: float
    sold_slots: int  # auctions with at least one seat sold
    fill_rate: float  # seats sold / seats offered on this pole


class SlotFinance(BaseModel):
    shift: str
    label: str
    revenue: int
    seats: int
    avg_price: int | None


class CategoryFinance(BaseModel):
    category: FootfallCategory
    revenue: int
    seats: int
    share: float


class FinanceDashboard(BaseModel):
    as_of: date
    window_start: date
    window_end: date
    granularity: str  # day | week | month
    kpis: FinanceKpis
    revenue: list[RevenueBucket]
    top_advertisers: list[AdvertiserFinance]  # by revenue
    frequent_buyers: list[AdvertiserFinance]  # by purchase days, then seats
    top_poles: list[PoleFinance]
    by_slot: list[SlotFinance]
    by_category: list[CategoryFinance]

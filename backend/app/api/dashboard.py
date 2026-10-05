from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Query
from pydantic import BaseModel
from sqlalchemy import select

from app.api.deps import AdminUser, AdvertiserUser, DbSession, OptionalUser
from app.models import AuctionRound, FootfallCategory, User, UserRole
from app.schemas.dashboard import AdvertiserDashboard, AuctionRow, BidHistoryPage, PoleAnalysis
from app.schemas.finance import FinanceDashboard
from app.services import dashboard_service, finance_service
from app.services.dashboard_service import OpportunityFilters

router = APIRouter(tags=["dashboards"])


@router.get("/dashboard/poles/{code}/analysis", response_model=PoleAnalysis)
def pole_analysis(code: str, db: DbSession, _admin: AdminUser) -> PoleAnalysis:
    """A pole's status, footfall, pricing and sales performance (admin)."""
    return dashboard_service.pole_analysis(db, code)


@router.get("/dashboard/advertiser", response_model=AdvertiserDashboard)
def advertiser_dashboard(db: DbSession, user: AdvertiserUser) -> AdvertiserDashboard:
    return dashboard_service.advertiser_dashboard(db, user)


@router.get("/dashboard/advertiser/bids", response_model=BidHistoryPage)
def advertiser_bids(
    db: DbSession,
    user: AdvertiserUser,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> BidHistoryPage:
    """Your bids, newest first, with what became of each."""
    return dashboard_service.bid_history(db, user, limit, offset)


@router.get("/dashboard/opportunities", response_model=list[AuctionRow])
def opportunities(
    db: DbSession,
    user: OptionalUser,
    date: date | None = None,
    shift: str | None = None,
    category: FootfallCategory | None = None,
    min_footfall: Annotated[int | None, Query(ge=0, description="Slot footfall")] = None,
    min_score: Annotated[int | None, Query(ge=0, le=100)] = None,
    max_price: Annotated[int | None, Query(gt=0, description="Max current minimum bid")] = None,
    round: AuctionRound | None = None,
    latitude: Annotated[float | None, Query(ge=-90, le=90)] = None,
    longitude: Annotated[float | None, Query(ge=-180, le=180)] = None,
    radius_km: Annotated[float | None, Query(gt=0, le=50)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 60,
) -> list[AuctionRow]:
    """Live auctions to bid on, busiest slots first. Signed-in advertisers
    also get their own seat and minimum bid per row."""
    f = OpportunityFilters(date, shift, category, min_footfall, min_score, max_price, round, latitude, longitude, radius_km, limit)
    viewer = user if user and user.role == UserRole.ADVERTISER else None
    return dashboard_service.opportunities(db, f, viewer)



@router.get("/dashboard/admin/finance", response_model=FinanceDashboard)
def admin_finance(
    db: DbSession,
    _admin: AdminUser,
    days: Annotated[int, Query(ge=0, le=3660, description="Window for charts and rankings in days; 0 = all time")] = 90,
    granularity: Annotated[Literal["day", "week", "month"], Query()] = "week",
) -> FinanceDashboard:
    """Revenue (today / 7 / 30 days / all time), revenue over time by round,
    top advertisers, frequent buyers, top poles, and revenue by slot and category."""
    return finance_service.finance_dashboard(db, days or None, granularity)


class UserBrief(BaseModel):
    id: int
    name: str
    email: str
    role: UserRole


@router.get("/users", response_model=list[UserBrief], tags=["auth"])
def list_users(db: DbSession, _admin: AdminUser, role: UserRole | None = None) -> list[UserBrief]:
    q = select(User).order_by(User.name)
    if role:
        q = q.where(User.role == role)
    return [UserBrief(id=u.id, name=u.name, email=u.email, role=u.role) for u in db.scalars(q)]

"""The admin's finance dashboard: revenue over time, top advertisers and poles.

Revenue is booked on the advertising date (the slot's date) when an auction
completes; each seat pays its own winning bid. There is no cost model, so
"profit" in the UI is this revenue.
"""

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import (
    Auction,
    AuctionStatus,
    Bid,
    FootfallCategory,
    InventorySlot,
    Pole,
    Road,
    User,
    WinningAdvertisement,
)
from app.schemas.finance import (
    AdvertiserFinance,
    CategoryFinance,
    FinanceDashboard,
    FinanceKpis,
    PeriodTotal,
    PoleFinance,
    RevenueBucket,
    SlotFinance,
)
from app.services import shifts as shift_svc

GRANULARITIES = ("day", "week", "month")
TOP_N = 10


@dataclass(frozen=True)
class Sale:
    """One sold seat."""

    day: date
    shift: str
    pole_id: int
    advertiser_id: int
    auction_id: int
    amount: int
    premium: bool


def _sales(db: Session, start: date | None, end: date) -> list[Sale]:
    """Sold seats with advertising dates in [start, end]."""
    q = (
        select(
            InventorySlot.date,
            InventorySlot.shift,
            InventorySlot.pole_id,
            WinningAdvertisement.advertiser_id,
            WinningAdvertisement.auction_id,
            WinningAdvertisement.winning_bid,
        )
        .select_from(WinningAdvertisement)
        .join(Auction, WinningAdvertisement.auction_id == Auction.id)
        .join(InventorySlot, Auction.inventory_slot_id == InventorySlot.id)
        .where(InventorySlot.date <= end)
    )
    if start is not None:
        q = q.where(InventorySlot.date >= start)
    rows = db.execute(q).all()
    # A seat is premium when the bid that won it was placed in the premium round.
    premium_bids = set(
        db.execute(
            select(Bid.auction_id, Bid.advertiser_id, Bid.amount).where(
                Bid.round == "PREMIUM", Bid.auction_id.in_(select(WinningAdvertisement.auction_id))
            )
        ).all()
    )
    return [Sale(d, s, p, a, au, amt, (au, a, amt) in premium_bids) for d, s, p, a, au, amt in rows]


def _bucket_start(d: date, granularity: str) -> date:
    if granularity == "week":
        return d - timedelta(days=d.weekday())
    if granularity == "month":
        return d.replace(day=1)
    return d


def _buckets(start: date, end: date, granularity: str) -> list[date]:
    out, d = [], _bucket_start(start, granularity)
    while d <= end:
        out.append(d)
        if granularity == "day":
            d += timedelta(days=1)
        elif granularity == "week":
            d += timedelta(days=7)
        else:
            d = (d.replace(day=28) + timedelta(days=4)).replace(day=1)
    return out


def _period(sales: list[Sale], end: date, days: int) -> PeriodTotal:
    start, prev_start = end - timedelta(days=days - 1), end - timedelta(days=2 * days - 1)
    cur = [s for s in sales if start <= s.day <= end]
    prev = [s for s in sales if prev_start <= s.day < start]
    return PeriodTotal(revenue=sum(s.amount for s in cur), seats=len(cur), previous_revenue=sum(s.amount for s in prev))


def _completed_auctions(db: Session, start: date, end: date) -> dict[int, int]:
    """Completed auctions in the window: auction id -> pole id."""
    rows = db.execute(
        select(Auction.id, InventorySlot.pole_id)
        .join(InventorySlot, Auction.inventory_slot_id == InventorySlot.id)
        .where(Auction.status == AuctionStatus.COMPLETED, InventorySlot.date.between(start, end))
    ).all()
    return dict(rows)


def _advertisers(db: Session, sales: list[Sale], completed: dict[int, int], total: int) -> list[AdvertiserFinance]:
    by_adv: dict[int, list[Sale]] = defaultdict(list)
    for s in sales:
        by_adv[s.advertiser_id].append(s)
    if not by_adv:
        return []
    names = dict(db.execute(select(User.id, User.name).where(User.id.in_(list(by_adv)))).all())
    bid_on: dict[int, int] = dict(
        db.execute(
            select(Bid.advertiser_id, func.count(func.distinct(Bid.auction_id)))
            .where(Bid.auction_id.in_(list(completed)), Bid.advertiser_id.in_(list(by_adv)))
            .group_by(Bid.advertiser_id)
        ).all()
    ) if completed else {}
    out = []
    for adv_id, rows in by_adv.items():
        revenue = sum(r.amount for r in rows)
        won = len({r.auction_id for r in rows})
        days = sorted({r.day for r in rows})
        bids = max(bid_on.get(adv_id, won), won)
        out.append(
            AdvertiserFinance(
                advertiser_id=adv_id,
                name=names.get(adv_id, f"Advertiser {adv_id}"),
                revenue=revenue,
                seats=len(rows),
                avg_price=round(revenue / len(rows)),
                share=round(revenue / total, 4) if total else 0.0,
                purchase_days=len(days),
                auctions_bid=bids,
                win_rate=round(won / bids, 3) if bids else 0.0,
                first_purchase=days[0],
                last_purchase=days[-1],
            )
        )
    return out


def _poles(db: Session, sales: list[Sale], completed: dict[int, int], total: int) -> list[PoleFinance]:
    by_pole: dict[int, list[Sale]] = defaultdict(list)
    for s in sales:
        by_pole[s.pole_id].append(s)
    offered: dict[int, int] = defaultdict(int)
    for pole_id in completed.values():
        offered[pole_id] += settings.seats_per_slot
    ranked = sorted(by_pole.items(), key=lambda kv: -sum(s.amount for s in kv[1]))[:TOP_N]
    if not ranked:
        return []
    poles = {
        p.id: (p, road)
        for p, road in db.execute(
            select(Pole, Road.name).outerjoin(Road, Pole.road_id == Road.id).where(Pole.id.in_([pid for pid, _ in ranked]))
        ).all()
    }
    out = []
    for pole_id, rows in ranked:
        pole, road = poles[pole_id]
        revenue = sum(r.amount for r in rows)
        out.append(
            PoleFinance(
                code=pole.code,
                name=pole.name,
                road_name=road,
                category=pole.category,
                revenue=revenue,
                seats=len(rows),
                avg_price=round(revenue / len(rows)),
                share=round(revenue / total, 4) if total else 0.0,
                sold_slots=len({r.auction_id for r in rows}),
                fill_rate=round(len(rows) / offered[pole_id], 3) if offered.get(pole_id) else 0.0,
            )
        )
    return out


def finance_dashboard(db: Session, days: int | None = 90, granularity: str = "week") -> FinanceDashboard:
    """``days`` = the window for charts and leaderboards (None = all time)."""
    if granularity not in GRANULARITIES:
        raise ValueError(f"granularity must be one of {GRANULARITIES}")
    today = shift_svc.local_today()
    all_sales = _sales(db, None, today)
    first = min((s.day for s in all_sales), default=today)
    start = first if days is None else today - timedelta(days=days - 1)
    window = [s for s in all_sales if start <= s.day <= today]
    total = sum(s.amount for s in window)
    completed = _completed_auctions(db, start, today)

    # Revenue over time, split by round.
    buckets = {b: [0, 0, 0] for b in _buckets(start, today, granularity)}
    for s in window:
        b = buckets[_bucket_start(s.day, granularity)]
        b[1 if s.premium else 0] += s.amount
        b[2] += 1

    advertisers = _advertisers(db, window, completed, total)
    buyers_by_day = [a for a in advertisers if a.purchase_days >= 2]

    pole_categories = dict(db.execute(select(Pole.id, Pole.category)).all())
    by_cat: dict[FootfallCategory, list[int]] = {c: [0, 0] for c in FootfallCategory}
    by_shift: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for s in window:
        by_cat[pole_categories[s.pole_id]][0] += s.amount
        by_cat[pole_categories[s.pole_id]][1] += 1
        by_shift[s.shift][0] += s.amount
        by_shift[s.shift][1] += 1

    return FinanceDashboard(
        as_of=today,
        window_start=start,
        window_end=today,
        granularity=granularity,
        kpis=FinanceKpis(
            today=_period(all_sales, today, 1),
            last_7_days=_period(all_sales, today, 7),
            last_30_days=_period(all_sales, today, 30),
            all_time_revenue=sum(s.amount for s in all_sales),
            all_time_seats=len(all_sales),
            avg_seat_price=round(total / len(window)) if window else None,
            seat_fill_rate=round(len(window) / (len(completed) * settings.seats_per_slot), 3) if completed else 0.0,
            premium_share=round(sum(s.amount for s in window if s.premium) / total, 3) if total else 0.0,
            active_buyers=len(advertisers),
            repeat_buyer_rate=round(len(buyers_by_day) / len(advertisers), 3) if advertisers else 0.0,
        ),
        revenue=[RevenueBucket(start=b, qualifying=v[0], premium=v[1], seats=v[2]) for b, v in buckets.items()],
        top_advertisers=sorted(advertisers, key=lambda a: -a.revenue)[:TOP_N],
        frequent_buyers=sorted(advertisers, key=lambda a: (-a.purchase_days, -a.seats))[:TOP_N],
        top_poles=_poles(db, window, completed, total),
        by_slot=[
            SlotFinance(
                shift=sh.code,
                label=sh.label,
                revenue=by_shift[sh.code][0],
                seats=by_shift[sh.code][1],
                avg_price=round(by_shift[sh.code][0] / by_shift[sh.code][1]) if by_shift[sh.code][1] else None,
            )
            for sh in shift_svc.list_shifts()
        ],
        by_category=[
            CategoryFinance(category=c, revenue=v[0], seats=v[1], share=round(v[0] / total, 4) if total else 0.0)
            for c, v in by_cat.items()
        ],
    )

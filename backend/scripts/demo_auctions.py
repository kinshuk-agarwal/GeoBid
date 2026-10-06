"""Hard-coded demo auctions so every slot on the map has data.

* Every slot of every pole for the next 7 days gets an auction on the
  standard schedule, advanced to where it would be right now:
  - tomorrow: past the 12:00 threshold (seats 1-2 confirmed; premium round
    from 16:00 today, with some premium bids already taking seats 3-4);
  - the following days: qualifying round (top 4 bidders hold seats).
* P014 16:00-18:00 is scripted for the demo:
  - tomorrow: advertisers 2 and 3 hold confirmed seats; seats 3-4 are held
    by qualifying bids from advertisers 4 and 5, so advertiser 1 can take
    seat 4 with a premium bid;
  - day after tomorrow: qualifying round, advertiser 1 hasn't bid yet.
* The last 6 months: completed auctions (revenue history for the finance dashboard).

Bids are generated with the same seat rules as live bidding (``seat_engine``)
and written in one transaction, so a running backend's auction worker never
sees a half-built auction.
"""

import random
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import Auction, AuctionStatus, Bid, InventorySlot, Pole, PoleStatus, SlotStatus, User, UserRole
from app.services import auction_service, inventory_service, seat_engine, slot_footfall_service, tariff_service
from app.services import shifts as shift_svc
from app.utils.time import utcnow

STEP_CHOICES = [1, 1, 1, 2, 3, 5]  # extra multiples of the ₹100 increment
# How many qualifying bids a slot attracts, by its footfall-based demand.
QUAL_BIDS = {
    "LOW": [0, 0, 0, 0, 1],
    "LOW_MEDIUM": [0, 0, 1, 2, 3],
    "MEDIUM": [1, 2, 3, 4, 5],
    "HIGH": [3, 4, 5, 6, 7],
    "VERY_HIGH": [4, 5, 6, 7, 8],
}
PREMIUM_BIDS = {"LOW": [0], "LOW_MEDIUM": [0, 0, 1], "MEDIUM": [0, 1, 1, 2], "HIGH": [0, 1, 2, 3], "VERY_HIGH": [1, 2, 3, 4]}

# Completed history for the finance dashboard.
HISTORY_DAYS = 180
# Relative purchase frequency of advertisers 1-8 (regulars buy more often).
BUYER_WEIGHTS = [4, 3, 3, 2, 2, 2, 1, 1]
# Live auctions (next 7 days): the chance a slot already has bids depends on
# its demand, the pole's footfall category and how soon it runs; busy slots
# draw 2-4 of the demo advertisers, quiet ones rarely any.
BID_CHANCE = {"LOW": 0.0, "LOW_MEDIUM": 0.03, "MEDIUM": 0.15, "HIGH": 0.55, "VERY_HIGH": 0.8}
CATEGORY_FACTOR = {"HIGH": 0.65, "MEDIUM": 0.1, "LOW": 0.02}
BIDDERS = {"LOW": (1, 1), "LOW_MEDIUM": (1, 2), "MEDIUM": (1, 2), "HIGH": (2, 3), "VERY_HIGH": (2, 4)}
RAISE_CHANCE = 0.35  # a bidder also raised their own bid
# Kept out of all demo bidding (a first-time bidder for testing).
FRESH_ACCOUNT = "newuser@geobid.local"
# How often each 2-hour slot (S1-S12) sells: nights rarely, evenings most.
SHIFT_SALES_WEIGHTS = [1, 1, 1, 2, 5, 4, 4, 4, 8, 8, 6, 2]


def _slot(db: Session, pole: Pole, day, shift: str, profile) -> InventorySlot:
    slot = db.scalar(
        select(InventorySlot).where(
            InventorySlot.pole_id == pole.id, InventorySlot.date == day, InventorySlot.shift == shift
        )
    )
    if slot is None:
        slot = inventory_service._new_slot(pole, day, shift, profile=profile)
        db.add(slot)
        db.flush()
    return slot


def _times(rng, t0: datetime, t1: datetime, n: int) -> list[datetime]:
    return sorted(t0 + (t1 - t0) * rng.random() for _ in range(n))


class _Sim:
    """Generates rule-abiding bids for one auction without going through the API."""

    def __init__(self, db, rng, a: Auction):
        self.db, self.rng, self.a = db, rng, a
        self.raw: list[tuple[int, int, str]] = []
        self.confirmed: list[seat_engine.BestBid] | None = None

    def best(self):
        return seat_engine.best_bids(self.raw)

    def bid(self, user: User, t: datetime, premium: bool) -> bool:
        a, n = self.a, settings.seats_per_slot
        mb = seat_engine.min_bid(
            user.id, self.best(), self.confirmed, premium, a.reserve_price, a.premium_floor, a.min_increment, n
        )
        if mb.amount is None:
            return False
        amount = mb.amount + (self.rng.choice(STEP_CHOICES) - 1) * a.min_increment
        while seat_engine.clashes(amount, user.id, self.best(), self.confirmed if premium else None, a.min_increment, n):
            amount += a.min_increment
        rnd = "PREMIUM" if premium else "QUALIFYING"
        self.raw.append((user.id, amount, rnd))
        self.db.add(Bid(auction_id=a.id, advertiser_id=user.id, amount=amount, round=rnd, timestamp=t))
        if amount > (a.current_highest_bid or 0):
            a.current_highest_bid, a.current_highest_bidder_id = amount, user.id
        return True


def build_auction(
    db,
    rng,
    slot: InventorySlot,
    now: datetime,
    bidders: list[User],
    demand: str,
    qualifying_plan: list[User] | None = None,
    premium_plan: list[User] | None = None,
) -> Auction:
    """An auction on the standard schedule, advanced to its state at ``now`` (no commit)."""
    s = auction_service.default_schedule(slot, now)
    # Opened 3 days before qualifying closes, but never in the future: every
    # demo slot is already open for bidding, so its bids must be in the past.
    start = min(s.qualifying_end - timedelta(days=3), now - timedelta(hours=12))
    a = Auction(
        inventory_slot=slot,
        start_time=start,
        qualifying_end_time=s.qualifying_end,
        premium_start_time=s.premium_start,
        end_time=s.end,
        reserve_price=slot.reserve_price,
        min_increment=auction_service.default_min_increment(slot.reserve_price),
        status=AuctionStatus.LIVE,
        created_at=start,
    )
    slot.status = SlotStatus.IN_AUCTION
    db.add(a)
    db.flush()
    sim = _Sim(db, rng, a)

    if qualifying_plan is None:
        qualifying_plan = [rng.choice(bidders) for _ in range(rng.choice(QUAL_BIDS[demand]))]
    q_until = min(now, s.qualifying_end) - timedelta(minutes=1)
    for user, t in zip(qualifying_plan, _times(rng, start, q_until, len(qualifying_plan))):
        sim.bid(user, t, premium=False)
    db.flush()

    if now >= s.qualifying_end:
        auction_service.confirm_seats(db, a, s.qualifying_end)
        sim.confirmed = [seat_engine.BestBid(c.advertiser_id, c.amount, "QUALIFYING") for c in a.confirmed_seats]
    if a.status == AuctionStatus.LIVE and now >= s.premium_start:
        auction_service.open_premium_round(a, s.premium_start)
        if premium_plan is None:
            confirmed_ids = {c.advertiser_id for c in a.confirmed_seats}
            pool = [b for b in bidders if b.id not in confirmed_ids]
            premium_plan = [rng.choice(pool) for _ in range(rng.choice(PREMIUM_BIDS[demand]))] if pool else []
        p_until = min(now, s.end) - timedelta(minutes=1)
        for user, t in zip(premium_plan, _times(rng, s.premium_start, p_until, len(premium_plan))):
            sim.bid(user, t, premium=True)
    db.flush()  # the session doesn't autoflush: closing must see the premium bids
    if a.status == AuctionStatus.LIVE and now >= s.end:
        auction_service.finalize_auction(db, a, s.end)
    db.flush()
    return a


def seed_demo_auctions(db: Session, now: datetime | None = None, seed: int = 7) -> dict:
    now = now or utcnow()
    rng = random.Random(seed)
    # Creation order = DEMO_USERS order (advertiser1, 2, ... 8).
    adv = sorted(
        db.scalars(select(User).where(User.role == UserRole.ADVERTISER, User.email != FRESH_ACCOUNT)), key=lambda u: u.id
    )
    a1, a2, a3, a4, a5 = adv[:5]
    poles = list(db.scalars(select(Pole).where(Pole.status == PoleStatus.ACTIVE).order_by(Pole.footfall.desc())))
    today = shift_svc.local_today()
    tomorrow = today + timedelta(days=1)
    shifts = [s.code for s in shift_svc.list_shifts()]
    profiles = slot_footfall_service.load_profiles(db, [p.id for p in poles])

    def demand(pole: Pole, day, shift: str) -> str:
        sf = slot_footfall_service.shift_footfall(profiles.get(pole.id), day, shift)
        return tariff_service.slot_demand(sf, pole.footfall, shift)

    def slot(pole, day, shift):
        return _slot(db, pole, day, shift, profiles.get(pole.id))

    # Completed history for the finance dashboard: HISTORY_DAYS back, growing
    # from ~1-2 to ~3-4 sold slots a day (one more at weekends). Regular
    # advertisers buy more often; busy slots sell more often.
    regulars = [u for u, w in zip(adv, BUYER_WEIGHTS) for _ in range(w)]
    pole_pool = poles[:45]
    for back in range(HISTORY_DAYS - 1, -1, -1):
        day = today - timedelta(days=back)
        growth = 1 - back / HISTORY_DAYS  # 0 six months ago -> 1 today
        n_slots = max(1, round(1.5 + 2 * growth) + (1 if day.weekday() >= 5 else 0) + rng.randint(-1, 1))
        picked: set[tuple[int, str]] = set()
        while len(picked) < n_slots:
            pole = pole_pool[min(int(rng.expovariate(1 / 12)), len(pole_pool) - 1)]  # busier poles sell more
            shift = rng.choices(shifts, weights=SHIFT_SALES_WEIGHTS)[0]
            if (pole.id, shift) in picked:
                continue
            picked.add((pole.id, shift))
            build_auction(db, rng, slot(pole, day, shift), now, regulars, demand(pole, day, shift))
        if back % 30 == 0:
            db.flush()

    # Every slot, the next 7 days, open for bidding. Busy slots on busy poles
    # attract several of the demo advertisers (more as the date gets closer);
    # quiet slots mostly have no bids yet. P014 16:00 is scripted below.
    def plan_for(pole: Pole, day, d: str) -> list[User]:
        ahead = (day - today).days
        chance = BID_CHANCE[d] * CATEGORY_FACTOR[pole.category.value] * (1.05 - 0.08 * ahead)
        if rng.random() >= chance:
            return []
        lo, hi = BIDDERS[d]
        bidders: list[User] = []
        while len(bidders) < rng.randint(lo, hi):
            u = rng.choices(adv, weights=BUYER_WEIGHTS)[0]
            if u not in bidders and not (pole.code == "P014" and u is a1):
                bidders.append(u)
        plan = bidders + [u for u in bidders if rng.random() < RAISE_CHANCE]
        rng.shuffle(plan)
        return plan

    for ahead in range(1, settings.inventory_days_ahead + 1):
        day = today + timedelta(days=ahead)
        for pole in poles:
            for shift in shifts:
                d = demand(pole, day, shift)
                s = slot(pole, day, shift)
                if pole.code == "P014" and shift == "S9" and day == tomorrow:
                    # confirmed: a2, a3 · provisional: a4, a5 · a1 can take seat 4 in premium
                    build_auction(db, rng, s, now, adv, d, qualifying_plan=[a5, a4, a3, a2, a3, a2], premium_plan=[])
                elif pole.code == "P014" and shift == "S9" and ahead == 2:
                    build_auction(db, rng, s, now, adv, d, qualifying_plan=[a2, a3, a4])
                else:
                    plan = plan_for(pole, day, d)
                    # Tomorrow's slots are already in the premium round: busy ones see premium bids too.
                    premium = None if plan and ahead == 1 and d in ("HIGH", "VERY_HIGH") else []
                    build_auction(db, rng, s, now, adv, d, qualifying_plan=plan, premium_plan=premium)
        db.flush()
    db.commit()

    stats = {"live": 0, "completed": 0}
    for (status,) in db.execute(
        select(Auction.status).where(Auction.status.in_([AuctionStatus.LIVE, AuctionStatus.COMPLETED]))
    ).all():
        stats["live" if status == AuctionStatus.LIVE else "completed"] += 1
    return stats

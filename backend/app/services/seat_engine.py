"""Seat rules for a slot's rolling ad (pure functions, no database).

A slot has ``n_seats`` (4) places in an equal rotation; each holder pays their
own bid. Seats are always derived from each advertiser's best bid:

* Qualifying round: the top 4 bidders hold seats 1-4. Seats 1-2 are on track
  to be confirmed; 3-4 are provisional.
* At 12:00 the top ``n_confirmed`` (2) are confirmed and can't be displaced.
* Premium round: anyone (except confirmed holders) may bid from the premium
  floor (1.5x the top bid). Premium bids outrank qualifying bids, so they take
  seat 4 first, then seat 3; after that the lowest premium seat can be taken
  by beating it by the increment.

Every bid must be at least ``increment`` away from every other seat holder's
bid, so no two seats ever hold the same amount.
"""

from dataclasses import dataclass

CONFIRMED = "CONFIRMED"  # secured at 12:00
LEADING = "LEADING"  # qualifying round, currently top 2 (will be confirmed)
PROVISIONAL = "PROVISIONAL"  # holds a seat with a qualifying-round bid; can be bumped
PREMIUM = "PREMIUM"  # holds a seat with a premium-round bid; can be bumped by a higher one
OPEN = "OPEN"  # empty seat


@dataclass(frozen=True)
class BestBid:
    advertiser_id: int
    amount: int
    round: str  # "QUALIFYING" | "PREMIUM"


@dataclass(frozen=True)
class Seat:
    seat: int  # 1-based
    advertiser_id: int | None
    amount: int | None
    status: str


@dataclass(frozen=True)
class MinBid:
    amount: int | None  # None = this user can't bid now
    reason: str | None = None


def best_bids(bids: list[tuple[int, int, str]]) -> list[BestBid]:
    """Each advertiser's highest bid, highest first. ``bids`` = (advertiser, amount, round)."""
    best: dict[int, BestBid] = {}
    for adv, amount, rnd in bids:
        if adv not in best or amount > best[adv].amount:
            best[adv] = BestBid(adv, amount, rnd)
    return sorted(best.values(), key=lambda b: -b.amount)


def _candidates(best: list[BestBid], confirmed: list[BestBid] | None, n_seats: int) -> list[BestBid]:
    """Holders of the seats that can still change hands."""
    if confirmed is None:
        return best[:n_seats]
    ids = {c.advertiser_id for c in confirmed}
    return [b for b in best if b.advertiser_id not in ids][: n_seats - len(confirmed)]


def seats(best: list[BestBid], confirmed: list[BestBid] | None, n_seats: int, n_confirmed: int) -> list[Seat]:
    out: list[Seat] = []
    if confirmed is None:  # qualifying round
        for i, b in enumerate(best[:n_seats]):
            out.append(Seat(i + 1, b.advertiser_id, b.amount, LEADING if i < n_confirmed else PROVISIONAL))
    else:
        for c in confirmed:
            out.append(Seat(len(out) + 1, c.advertiser_id, c.amount, CONFIRMED))
        for b in _candidates(best, confirmed, n_seats):
            out.append(Seat(len(out) + 1, b.advertiser_id, b.amount, PREMIUM if b.round == "PREMIUM" else PROVISIONAL))
    while len(out) < n_seats:
        out.append(Seat(len(out) + 1, None, None, OPEN))
    return out


def min_bid(
    user_id: int | None,
    best: list[BestBid],
    confirmed: list[BestBid] | None,
    premium: bool,
    base: int,
    floor: int | None,
    increment: int,
    n_seats: int,
) -> MinBid:
    """Lowest amount ``user_id`` may bid right now (``None`` user = a newcomer).

    Never an amount within ``increment`` of another seat holder's bid.
    """
    mb = _raw_min_bid(user_id, best, confirmed, premium, base, floor, increment, n_seats)
    if mb.amount is None:
        return mb
    amount = mb.amount
    while clashes(amount, user_id, best, confirmed if premium else None, increment, n_seats) is not None:
        amount += increment
    return MinBid(amount)


def _raw_min_bid(
    user_id: int | None,
    best: list[BestBid],
    confirmed: list[BestBid] | None,
    premium: bool,
    base: int,
    floor: int | None,
    increment: int,
    n_seats: int,
) -> MinBid:
    if not premium:
        holders = best[:n_seats]
        own = next((b for b in holders if b.advertiser_id == user_id), None)
        if own:
            return MinBid(own.amount + increment)  # raising your own bid
        if len(holders) < n_seats:
            return MinBid(base)
        return MinBid(max(base, holders[-1].amount + increment))

    confirmed = confirmed or []
    if user_id is not None and any(c.advertiser_id == user_id for c in confirmed):
        return MinBid(None, "You already hold a confirmed seat")
    floor = floor or base
    holders = _candidates(best, confirmed, n_seats)
    open_seats = n_seats - len(confirmed)
    own = next((b for b in holders if b.advertiser_id == user_id), None)
    if own and own.amount >= floor:
        return MinBid(own.amount + increment)  # raising your own premium bid
    if len(holders) < open_seats or any(h.amount < floor for h in holders):
        return MinBid(floor)  # a seat is empty or still held by a qualifying bid
    return MinBid(min(h.amount for h in holders) + increment)


def clashes(
    amount: int, user_id: int | None, best: list[BestBid], confirmed: list[BestBid] | None, increment: int, n_seats: int
) -> int | None:
    """A seat holder's bid within ``increment`` of ``amount`` (matching bids aren't allowed)."""
    for h in _candidates(best, confirmed, n_seats):
        if h.advertiser_id != user_id and abs(h.amount - amount) < increment:
            return h.amount
    return None


def premium_floor(top_bid: int | None, base: int, multiplier: float, step: int) -> int:
    """``multiplier`` x the top qualifying bid (or base price), rounded up to ``step``."""
    raw = round((top_bid or base) * multiplier, 6)
    return int(-(-raw // step) * step)

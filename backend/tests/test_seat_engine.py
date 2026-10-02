"""Pure seat-rule tests (no database)."""

from app.services import seat_engine as se

B = se.BestBid
BASE, INC, N = 5_000, 100, 4


def q(*pairs):
    """Best bids from (advertiser, amount) pairs placed in the qualifying round."""
    return se.best_bids([(a, x, "QUALIFYING") for a, x in pairs])


def test_best_bid_per_advertiser():
    best = se.best_bids([(1, 5_000, "QUALIFYING"), (2, 5_200, "QUALIFYING"), (1, 5_400, "QUALIFYING")])
    assert [(b.advertiser_id, b.amount) for b in best] == [(1, 5_400), (2, 5_200)]


def test_qualifying_seats_and_open_seats():
    seats = se.seats(q((1, 5_300), (2, 5_100)), None, N, 2)
    assert [(s.seat, s.advertiser_id, s.status) for s in seats] == [
        (1, 1, se.LEADING), (2, 2, se.LEADING), (3, None, se.OPEN), (4, None, se.OPEN),
    ]


def test_qualifying_min_bid():
    best = q((1, 5_300), (2, 5_100))
    assert se.min_bid(None, best, None, False, BASE, None, INC, N).amount == BASE  # seats free
    full = q((1, 5_600), (2, 5_400), (3, 5_200), (4, 5_000))
    assert se.min_bid(None, full, None, False, BASE, None, INC, N).amount == 5_100  # beat seat 4
    assert se.min_bid(4, full, None, False, BASE, None, INC, N).amount == 5_100  # raise own bid by the increment


def test_min_bid_skips_amounts_already_held():
    best = q((1, 5_200), (2, 5_100), (3, 5_000))
    assert se.min_bid(None, best, None, False, BASE, None, INC, N).amount == 5_300


def test_clash_detection():
    best = q((1, 5_600), (2, 5_400))
    assert se.clashes(5_400, 9, best, None, INC, N) == 5_400
    assert se.clashes(5_450, 9, best, None, INC, N) == 5_400
    assert se.clashes(5_500, 9, best, None, INC, N) is None
    assert se.clashes(5_400, 2, best, None, INC, N) is None  # your own bid doesn't clash


def test_premium_floor():
    assert se.premium_floor(9_700, BASE, 1.5, 100) == 14_600  # 14,550 rounded up
    assert se.premium_floor(None, BASE, 1.5, 100) == 7_500  # no bids: 1.5x base


def test_premium_takes_seat_4_then_3_then_lowest_premium():
    confirmed = [B(1, 6_000, "QUALIFYING"), B(2, 5_800, "QUALIFYING")]
    raw = [(1, 6_000, "QUALIFYING"), (2, 5_800, "QUALIFYING"), (3, 5_600, "QUALIFYING"), (4, 5_400, "QUALIFYING")]
    floor = 9_000

    def state():
        best = se.best_bids(raw)
        return best, se.seats(best, confirmed, N, 2)

    best, seats = state()
    assert [s.status for s in seats] == [se.CONFIRMED, se.CONFIRMED, se.PROVISIONAL, se.PROVISIONAL]
    assert se.min_bid(None, best, confirmed, True, BASE, floor, INC, N).amount == floor

    raw.append((5, 9_000, "PREMIUM"))  # newcomer takes a seat: advertiser 4 (seat 4) is bumped
    best, seats = state()
    assert [s.advertiser_id for s in seats] == [1, 2, 5, 3]
    assert seats[2].status == se.PREMIUM and seats[3].status == se.PROVISIONAL
    # a seat is still held by a qualifying bid, so the floor applies, but 9,000 is taken
    assert se.min_bid(None, best, confirmed, True, BASE, floor, INC, N).amount == floor + INC

    raw.append((6, 9_200, "PREMIUM"))  # next premium bid bumps advertiser 3 (old seat 3)
    best, seats = state()
    assert [s.advertiser_id for s in seats] == [1, 2, 6, 5]
    # both open seats are premium now: must beat the lowest (9,000) by the increment
    assert se.min_bid(None, best, confirmed, True, BASE, floor, INC, N).amount == 9_100

    raw.append((4, 9_100, "PREMIUM"))  # a bumped bidder comes back and takes the lowest seat
    best, seats = state()
    assert [s.advertiser_id for s in seats] == [1, 2, 6, 4]


def test_confirmed_holders_cannot_bid_in_premium():
    confirmed = [B(1, 6_000, "QUALIFYING"), B(2, 5_800, "QUALIFYING")]
    best = se.best_bids([(1, 6_000, "QUALIFYING"), (2, 5_800, "QUALIFYING")])
    mb = se.min_bid(1, best, confirmed, True, BASE, 9_000, INC, N)
    assert mb.amount is None and "confirmed" in mb.reason


def test_premium_seat_holder_can_raise():
    confirmed = [B(1, 6_000, "QUALIFYING"), B(2, 5_800, "QUALIFYING")]
    best = se.best_bids([(1, 6_000, "QUALIFYING"), (2, 5_800, "QUALIFYING"), (5, 9_000, "PREMIUM")])
    assert se.min_bid(5, best, confirmed, True, BASE, 9_000, INC, N).amount == 9_100

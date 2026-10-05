from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy.orm.attributes import set_committed_value

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.exceptions import BusinessRuleError, ConflictError, PermissionDeniedError
from app.models import (
    Auction,
    AuctionRound,
    AuctionStatus,
    Bid,
    InventorySlot,
    Pole,
    SlotPriceHistory,
    SlotStatus,
    User,
    UserRole,
    WinningAdvertisement,
)
from app.services import auction_service, inventory_service, slot_footfall_service
from app.services import shifts as shift_svc
from app.services.events import EventType
from app.utils.time import utcnow
from scripts.seed_database import seed_all


@pytest.fixture
def seeded(db, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "synthetic_data_dir", tmp_path)
    seed_all(db, tmp_path, demo_auctions=False, price_history=False)
    return db


@pytest.fixture
def slot(seeded) -> InventorySlot:
    """Tomorrow's 16:00-18:00 slot for P014."""
    pole = seeded.query(Pole).filter_by(code="P014").one()
    return seeded.query(InventorySlot).filter_by(pole_id=pole.id, date=shift_svc.tomorrow(), shift="S9").one()


@pytest.fixture
def adv(make_user):
    """Six advertisers."""
    return [make_user(f"adv{i}@example.com", UserRole.ADVERTISER) for i in range(6)]


def live_auction(db, slot, q_min=30, gap_min=30, premium_min=60) -> Auction:
    """A LIVE auction on a compressed schedule relative to now."""
    now = utcnow()
    q_end = now + timedelta(minutes=q_min)
    premium = q_end + timedelta(minutes=gap_min)
    auction, events = auction_service.create_auction(
        db,
        slot_id=slot.id,
        qualifying_end_time=q_end,
        premium_start_time=premium,
        end_time=premium + timedelta(minutes=premium_min),
        now=now,
    )
    assert auction.status == AuctionStatus.LIVE and auction.round == AuctionRound.QUALIFYING
    assert [e.type for e in events] == [EventType.AUCTION_STARTED]
    return auction


def bid(db, a, user, amount, at=None):
    return auction_service.place_bid(db, a.id, user, amount, now=at)


def seat_ids(db, a):
    db.refresh(a)
    return [s.advertiser_id for s in auction_service.seat_state(db, a).seats]


def fill_qualifying(db, a, adv):
    """adv0..adv3 at R+300, R+200, R+100, R  ->  seats [adv0, adv1, adv2, adv3]."""
    r = a.reserve_price
    for user, amount in [(adv[3], r), (adv[2], r + 100), (adv[1], r + 200), (adv[0], r + 300)]:
        bid(db, a, user, amount)


def to_premium(db, a):
    auction_service.process_due(db, now=a.qualifying_end_time)
    auction_service.process_due(db, now=a.premium_start_time)
    db.refresh(a)


# --- schedule & creation ------------------------------------------------------------


def test_default_schedule_follows_business_rules():
    s_ = InventorySlot(date=date(2026, 10, 3), shift="S9", pole_id=1, base_tariff=1, reserve_price=1)
    s = auction_service.default_schedule(s_, now=utcnow())
    utc = timezone.utc
    assert s.qualifying_end == datetime(2026, 10, 2, 6, 30, tzinfo=utc)  # 12:00 IST day before
    assert s.premium_start == datetime(2026, 10, 2, 10, 30, tzinfo=utc)  # 16:00 IST day before
    assert s.end == datetime(2026, 10, 3, 8, 30, tzinfo=utc)  # 2h before the 16:00 slot


def test_seven_days_of_inventory(seeded):
    n = seeded.query(Pole).count()
    for ahead in range(1, 8):
        day = shift_svc.local_today() + timedelta(days=ahead)
        assert seeded.query(InventorySlot).filter_by(date=day).count() == 12 * n


def test_create_marks_slot_and_uses_100_step(seeded, slot):
    a = live_auction(seeded, slot)
    assert a.min_increment == 100
    seeded.refresh(slot)
    assert slot.status == SlotStatus.IN_AUCTION


def test_cannot_create_after_threshold(seeded, slot):
    after = auction_service.default_schedule(slot, utcnow()).qualifying_end + timedelta(minutes=1)
    with pytest.raises(BusinessRuleError, match="qualifying round for this slot closed"):
        auction_service.create_auction(seeded, slot_id=slot.id, now=after)


def test_one_auction_per_slot(seeded, slot):
    live_auction(seeded, slot)
    with pytest.raises(ConflictError):
        live_auction(seeded, slot)


# --- qualifying round: 4 seats -----------------------------------------------------------


def test_top_four_hold_seats(seeded, slot, adv):
    a = live_auction(seeded, slot)
    fill_qualifying(seeded, a, adv)
    assert seat_ids(seeded, a) == [adv[0].id, adv[1].id, adv[2].id, adv[3].id]


def test_newcomer_must_beat_seat_four_and_bumps_it(seeded, slot, adv):
    a = live_auction(seeded, slot)
    fill_qualifying(seeded, a, adv)
    r = a.reserve_price
    with pytest.raises(BusinessRuleError, match="All open seats are taken"):
        bid(seeded, a, adv[4], r)
    res = bid(seeded, a, adv[4], r + 400)  # takes the top; adv3 (lowest) is bumped
    assert res.bumped == [adv[3].id]
    assert [e.type for e in res.events] == [EventType.NEW_BID, EventType.OUTBID]
    assert res.events[1].data["outbid_user_id"] == adv[3].id
    assert seat_ids(seeded, a) == [adv[4].id, adv[0].id, adv[1].id, adv[2].id]


def test_matching_bids_rejected(seeded, slot, adv):
    a = live_auction(seeded, slot)
    r = a.reserve_price
    bid(seeded, a, adv[0], r + 1_000)
    with pytest.raises(BusinessRuleError, match="Matching bids are not allowed"):
        bid(seeded, a, adv[1], r + 1_000)
    with pytest.raises(BusinessRuleError, match="Matching"):
        bid(seeded, a, adv[1], r + 1_050)  # within ₹100
    assert bid(seeded, a, adv[1], r + 1_100)


def test_raise_own_bid(seeded, slot, adv):
    a = live_auction(seeded, slot)
    fill_qualifying(seeded, a, adv)
    with pytest.raises(BusinessRuleError, match="To raise your bid"):
        bid(seeded, a, adv[3], a.reserve_price + 50)
    bid(seeded, a, adv[3], a.reserve_price + 500)  # seat 4 -> seat 1
    assert seat_ids(seeded, a)[0] == adv[3].id


def test_base_price_and_roles(seeded, slot, adv, make_user):
    a = live_auction(seeded, slot)
    with pytest.raises(BusinessRuleError, match="base price"):
        bid(seeded, a, adv[0], a.reserve_price - 100)
    with pytest.raises(PermissionDeniedError):
        bid(seeded, a, make_user("o@example.com", UserRole.ADMIN), a.reserve_price)


def test_bidding_starts_at_footfall_priced_base(seeded, slot, adv):
    pole = slot.pole
    profile = slot_footfall_service.load_profiles(seeded, [pole.id]).get(pole.id)
    quote = inventory_service.quote_slot(pole, slot.date, slot.shift, profile)
    assert quote.basis == "slot_footfall"
    a = live_auction(seeded, slot)
    assert a.reserve_price == quote.reserve_price > settings.base_tariff_inr
    with pytest.raises(BusinessRuleError, match="base price"):
        bid(seeded, a, adv[0], settings.base_tariff_inr)


def test_stale_bid_loses_race(seeded, slot, adv):
    """adv1 validated against an older version; the conditional update must reject it."""
    a = live_auction(seeded, slot)
    bid(seeded, a, adv[0], a.reserve_price)
    with SessionLocal() as stale:
        cached = stale.get(Auction, a.id)
        set_committed_value(cached, "version", cached.version - 1)
        with pytest.raises(ConflictError, match="Another bid"):
            auction_service.place_bid(stale, a.id, stale.get(User, adv[1].id), a.reserve_price + 500)


# --- 12:00 threshold, premium round ---------------------------------------------------


def test_threshold_confirms_top_two_and_sets_floor(seeded, slot, adv):
    a = live_auction(seeded, slot)
    fill_qualifying(seeded, a, adv)
    events = auction_service.process_due(seeded, now=a.qualifying_end_time)
    assert [e.type for e in events] == [EventType.QUALIFYING_CLOSED]
    seeded.refresh(a)
    assert a.round == AuctionRound.BREAK
    assert [(c.seat, c.advertiser_id) for c in a.confirmed_seats] == [(1, adv[0].id), (2, adv[1].id)]
    top = a.reserve_price + 300
    assert a.premium_floor == -(-int(top * 1.5) // 100) * 100
    statuses = [s["status"] for s in events[0].data["seats"]]
    assert statuses == ["CONFIRMED", "CONFIRMED", "PROVISIONAL", "PROVISIONAL"]


def test_no_bidding_during_break(seeded, slot, adv):
    a = live_auction(seeded, slot)
    fill_qualifying(seeded, a, adv)
    with pytest.raises(BusinessRuleError, match="qualifying round has closed"):
        bid(seeded, a, adv[4], 99_999, at=a.qualifying_end_time + timedelta(minutes=1))


def test_premium_bids_take_seat_four_then_three(seeded, slot, adv):
    a = live_auction(seeded, slot)
    fill_qualifying(seeded, a, adv)
    to_premium(seeded, a)
    floor, t = a.premium_floor, a.premium_start_time + timedelta(minutes=1)

    with pytest.raises(BusinessRuleError, match="Premium bids start at"):
        bid(seeded, a, adv[4], floor - 100, at=t)
    r1 = bid(seeded, a, adv[4], floor, at=t)  # newcomer: bumps adv3 (seat 4)
    assert r1.bumped == [adv[3].id]
    assert seat_ids(seeded, a) == [adv[0].id, adv[1].id, adv[4].id, adv[2].id]

    r2 = bid(seeded, a, adv[5], floor + 200, at=t)  # bumps adv2 (old seat 3)
    assert r2.bumped == [adv[2].id]
    assert seat_ids(seeded, a) == [adv[0].id, adv[1].id, adv[5].id, adv[4].id]

    # a bumped bidder can come back by beating the lowest premium seat
    r3 = bid(seeded, a, adv[3], floor + 100, at=t)
    assert r3.bumped == [adv[4].id]
    assert seat_ids(seeded, a) == [adv[0].id, adv[1].id, adv[5].id, adv[3].id]


def test_confirmed_holders_do_not_bid_in_premium(seeded, slot, adv):
    a = live_auction(seeded, slot)
    fill_qualifying(seeded, a, adv)
    to_premium(seeded, a)
    with pytest.raises(BusinessRuleError, match="confirmed seat"):
        bid(seeded, a, adv[0], a.premium_floor, at=a.premium_start_time)


def test_close_books_every_seat_at_its_own_bid(seeded, slot, adv):
    a = live_auction(seeded, slot)
    fill_qualifying(seeded, a, adv)
    to_premium(seeded, a)
    floor = a.premium_floor
    bid(seeded, a, adv[4], floor, at=a.premium_start_time)
    events = auction_service.process_due(seeded, now=a.end_time)
    done = events[0]
    assert done.type == EventType.AUCTION_COMPLETED
    r = a.reserve_price
    assert [(w["seat"], w["advertiser_id"], w["amount"]) for w in done.data["winners"]] == [
        (1, adv[0].id, r + 300),
        (2, adv[1].id, r + 200),
        (3, adv[4].id, floor),
        (4, adv[2].id, r + 100),
    ]
    assert done.data["revenue"] == (r + 300) + (r + 200) + floor + (r + 100)
    rows = seeded.query(WinningAdvertisement).filter_by(auction_id=a.id).order_by(WinningAdvertisement.seat).all()
    assert [w.advertiser_id for w in rows] == [adv[0].id, adv[1].id, adv[4].id, adv[2].id]
    seeded.refresh(slot)
    assert slot.status == SlotStatus.SOLD
    hist = seeded.query(SlotPriceHistory).filter_by(pole_id=slot.pole_id, date=slot.date, shift="S9").one()
    assert hist.clearing_price == round(done.data["revenue"] / 4) and hist.source == "auction"


def test_unsold_when_nobody_bids(seeded, slot):
    a = live_auction(seeded, slot)
    events = auction_service.process_due(seeded, now=a.end_time)
    assert events[-1].type == EventType.AUCTION_COMPLETED and events[-1].data["winners"] == []
    seeded.refresh(slot)
    assert slot.status == SlotStatus.UNSOLD


def test_fewer_bidders_leave_seats_open_for_premium(seeded, slot, adv):
    a = live_auction(seeded, slot)
    bid(seeded, a, adv[0], a.reserve_price)
    to_premium(seeded, a)
    assert [c.advertiser_id for c in a.confirmed_seats] == [adv[0].id]
    bid(seeded, a, adv[1], a.premium_floor, at=a.premium_start_time)
    assert seat_ids(seeded, a)[:2] == [adv[0].id, adv[1].id]


def test_advance_round_for_demo(seeded, slot, adv):
    a = live_auction(seeded, slot)
    fill_qualifying(seeded, a, adv)
    assert [e.type for e in auction_service.advance_round(seeded, a.id)] == [EventType.QUALIFYING_CLOSED]
    assert [e.type for e in auction_service.advance_round(seeded, a.id)] == [EventType.PREMIUM_ROUND_STARTED]
    seeded.refresh(a)
    bid(seeded, a, adv[4], a.premium_floor)
    done = auction_service.advance_round(seeded, a.id)
    assert done[0].type == EventType.AUCTION_COMPLETED and len(done[0].data["winners"]) == 4


def test_expired_and_completed_reject_bids(seeded, slot, adv):
    a = live_auction(seeded, slot)
    with pytest.raises(BusinessRuleError, match="expired"):
        bid(seeded, a, adv[0], a.reserve_price, at=a.end_time)
    auction_service.complete_auction(seeded, a.id)
    with pytest.raises(BusinessRuleError, match="ended"):
        bid(seeded, a, adv[0], a.reserve_price)


# --- API ------------------------------------------------------------------------------


def test_auction_api_seats_and_viewer(client, seeded, slot, auth_headers):
    admin = auth_headers("root@example.com", UserRole.ADMIN)
    h = [auth_headers(f"a{i}@example.com") for i in range(5)]
    now = utcnow()
    res = client.post(
        "/api/auctions",
        json={
            "inventory_slot_id": slot.id,
            "qualifying_end_time": (now + timedelta(minutes=30)).isoformat(),
            "premium_start_time": (now + timedelta(minutes=60)).isoformat(),
            "end_time": (now + timedelta(minutes=120)).isoformat(),
        },
        headers=admin,
    )
    assert res.status_code == 201, res.text
    a = res.json()
    aid, r = a["id"], a["reserve_price"]
    assert a["seats_total"] == 4 and [s["status"] for s in a["seats"]] == ["OPEN"] * 4

    for i, amount in enumerate([r, r + 100, r + 200, r + 300]):
        assert client.post(f"/api/auctions/{aid}/bids", json={"amount": amount}, headers=h[i]).status_code == 201
    view = client.get(f"/api/auctions/{aid}", headers=h[0]).json()
    assert view["viewer"]["seat"] == 4 and view["viewer"]["next_min_bid"] == r + 400  # raise past held amounts
    assert client.get(f"/api/auctions/{aid}", headers=h[4]).json()["viewer"]["next_min_bid"] == r + 400
    assert client.get(f"/api/auctions/{aid}").json()["viewer"] is None

    q = client.post(f"/api/auctions/{aid}/advance", headers=admin).json()
    assert q["round"] == "BREAK" and [s["status"] for s in q["seats"]][:2] == ["CONFIRMED", "CONFIRMED"]
    p = client.post(f"/api/auctions/{aid}/advance", headers=admin).json()
    floor = p["premium_floor"]
    assert p["round"] == "PREMIUM" and p["next_min_bid"] == floor
    v3 = client.get(f"/api/auctions/{aid}", headers=h[3]).json()["viewer"]
    assert v3["seat_status"] == "CONFIRMED" and v3["can_bid"] is False
    assert client.post(f"/api/auctions/{aid}/bids", json={"amount": floor}, headers=h[4]).status_code == 201

    done = client.post(f"/api/auctions/{aid}/complete", headers=admin).json()
    assert done["status"] == "COMPLETED" and len(done["winners"]) == 4 and done["slot_status"] == "SOLD"
    assert done["revenue"] == sum(w["amount"] for w in done["winners"])


def test_create_auction_requires_admin(client, seeded, slot, auth_headers):
    res = client.post("/api/auctions", json={"inventory_slot_id": slot.id}, headers=auth_headers("a1@example.com"))
    assert res.status_code == 403


def test_demo_seed(db, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "synthetic_data_dir", tmp_path)
    summary = seed_all(db, tmp_path, price_history=False)
    assert summary["live"] > 0 and summary["completed"] > 0
    pole = db.query(Pole).filter_by(code="P014").one()
    tomorrow = (
        db.query(Auction)
        .join(InventorySlot)
        .filter(InventorySlot.pole_id == pole.id, InventorySlot.date == shift_svc.tomorrow(), InventorySlot.shift == "S9")
        .one()
    )
    # Tomorrow's qualifying round closes at 12:00 today, so its state depends on the clock.
    if utcnow() >= tomorrow.qualifying_end_time:
        assert tomorrow.round in (AuctionRound.BREAK, AuctionRound.PREMIUM) and len(tomorrow.confirmed_seats) == 2
    else:
        assert tomorrow.round == AuctionRound.QUALIFYING and not tomorrow.confirmed_seats
    assert db.query(WinningAdvertisement).count() > 0
    assert db.query(Bid).filter(Bid.timestamp > utcnow()).count() == 0  # demo bids are all in the past
    # Premium bids count when past auctions close: some sold seats were won in the premium round.
    premium_wins = (
        db.query(WinningAdvertisement)
        .join(Bid, (Bid.auction_id == WinningAdvertisement.auction_id) & (Bid.advertiser_id == WinningAdvertisement.advertiser_id)
              & (Bid.amount == WinningAdvertisement.winning_bid))
        .filter(Bid.round == "PREMIUM")
        .count()
    )
    assert premium_wins > 0

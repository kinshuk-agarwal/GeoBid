from datetime import timedelta

import pytest

from app.core.config import settings
from app.models import InventorySlot, Pole, SlotPriceHistory, UserRole
from app.services import auction_service, price_trend_service
from app.services import shifts as shift_svc
from app.synthetic.price_history import backfill_price_history
from app.utils.time import utcnow
from scripts.seed_database import seed_all


@pytest.fixture
def seeded(db, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "synthetic_data_dir", tmp_path)
    seed_all(db, tmp_path, demo_auctions=False)
    return db


@pytest.mark.parametrize(
    "value, expected",
    [(425, (400, 450)), (9_430, (9_000, 10_000)), (16_300, (16_000, 17_000)), (6_014, (6_000, 6_500)), (95, (90, 100))],
)
def test_price_range_buckets(value, expected):
    assert price_trend_service.price_range(value) == expected


def test_backfill_covers_two_months_and_is_idempotent(seeded):
    n_poles = seeded.query(Pole).count()
    rows = seeded.query(SlotPriceHistory).count()
    assert rows == n_poles * 12 * settings.price_trend_days
    assert backfill_price_history(seeded) == 0  # nothing missing


def test_backfill_shape(seeded):
    rows = seeded.query(SlotPriceHistory).all()
    assert all(r.clearing_price is None or r.clearing_price >= r.base_price for r in rows)
    assert all(r.clearing_price is None or r.clearing_price % 100 == 0 for r in rows)

    def unsold_rate(shift):
        rs = [r for r in rows if r.shift == shift]
        return sum(r.clearing_price is None for r in rs) / len(rs)

    assert unsold_rate("S2") > unsold_rate("S9")  # 02:00-04:00 sells less often than 16:00-18:00

    def avg(pred):
        xs = [r.clearing_price / r.base_price for r in rows if r.clearing_price and pred(r)]
        return sum(xs) / len(xs)

    # busy evening slots draw more competition above base than night slots
    assert avg(lambda r: r.shift == "S10") > avg(lambda r: r.shift == "S2")


def test_expected_price_uses_same_weekday_and_shift(seeded):
    pole = seeded.query(Pole).filter_by(code="P014").one()
    seeded.query(SlotPriceHistory).filter_by(pole_id=pole.id).delete()
    today = shift_svc.local_today()
    saturdays = [d for d in (today - timedelta(days=i) for i in range(1, 60)) if d.weekday() == 5][:4]
    for d, price in zip(saturdays, [400, 420, 430, 450]):  # average 425
        seeded.add(SlotPriceHistory(pole_id=pole.id, date=d, shift="S9", base_price=300, clearing_price=price))
    seeded.add(SlotPriceHistory(pole_id=pole.id, date=saturdays[0] - timedelta(days=1), shift="S9",
                                base_price=300, clearing_price=9_999))  # a Friday: must not count
    seeded.add(SlotPriceHistory(pole_id=pole.id, date=saturdays[1], shift="S10",
                                base_price=300, clearing_price=9_999))  # other shift: must not count
    seeded.commit()

    table = price_trend_service.expected_prices(seeded, [pole.id])
    e = price_trend_service.expected_for(table, pole.id, "S9", saturdays[0] + timedelta(days=7))
    assert (e.average, e.low, e.high, e.samples, e.weekday_label) == (425, 400, 450, 4, "Sat")


def test_inventory_and_trend_api(client, seeded):
    inv = client.get("/api/poles/P014/inventory").json()
    s9 = next(s for s in inv["slots"] if s["shift"] == "S9")
    e = s9["expected_price"]
    assert e and e["low"] <= e["average"] < e["high"] and e["samples"] > 0

    tomorrow = shift_svc.tomorrow()
    body = client.get("/api/poles/P014/price-trend", params={"shift": "S9"}).json()
    assert len(body["points"]) == settings.price_trend_days
    assert [w["weekday"] for w in body["by_weekday"]] == ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    assert body["target_date"] == tomorrow.isoformat()
    assert body["expected"]["weekday"] == price_trend_service.WEEKDAYS[tomorrow.weekday()]
    assert body["expected"] == e  # same figure as the inventory slot shows
    assert 0 < body["sell_through"] <= 1 and body["synthetic_share"] == 1.0
    assert client.get("/api/poles/P014/price-trend", params={"shift": "S99"}).status_code == 404


def test_completed_auction_feeds_history(seeded, make_user):
    adv = make_user("adv@example.com", UserRole.ADVERTISER)
    pole = seeded.query(Pole).filter_by(code="P014").one()
    slot = seeded.query(InventorySlot).filter_by(pole_id=pole.id, date=shift_svc.tomorrow(), shift="S9").one()
    now = utcnow()
    a, _ = auction_service.create_auction(
        seeded, slot_id=slot.id, qualifying_end_time=now + timedelta(minutes=30),
        premium_start_time=now + timedelta(minutes=60), end_time=now + timedelta(minutes=120), now=now,
    )
    auction_service.place_bid(seeded, a.id, adv, a.reserve_price + 300)
    auction_service.complete_auction(seeded, a.id)
    row = seeded.query(SlotPriceHistory).filter_by(pole_id=pole.id, date=slot.date, shift="S9").one()
    assert (row.clearing_price, row.bid_count, row.source) == (a.reserve_price + 300, 1, "auction")

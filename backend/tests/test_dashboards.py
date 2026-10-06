from datetime import timedelta

import pytest

from app.core.config import settings
from app.models import InventorySlot, Pole, UserRole
from app.services import auction_service
from app.services import shifts as shift_svc
from app.utils.time import utcnow
from scripts.seed_database import seed_all


@pytest.fixture
def seeded(db, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "synthetic_data_dir", tmp_path)
    seed_all(db, tmp_path, demo_auctions=False, price_history=False)
    return db


def login(client, email):
    res = client.post("/api/auth/login", json={"email": email, "password": "geobid123"})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


@pytest.fixture
def p014_auction(seeded):
    """A live auction for tomorrow's 16:00-18:00 P014 slot."""
    pole = seeded.query(Pole).filter_by(code="P014").one()
    slot = seeded.query(InventorySlot).filter_by(pole_id=pole.id, date=shift_svc.tomorrow(), shift="S9").one()
    now = utcnow()
    a, _ = auction_service.create_auction(
        seeded,
        slot_id=slot.id,
        qualifying_end_time=now + timedelta(minutes=30),
        premium_start_time=now + timedelta(minutes=60),
        end_time=now + timedelta(minutes=120),
        now=now,
    )
    return a


def test_dashboards_follow_an_auction_to_completion(client, seeded, p014_auction):
    a = p014_auction
    adv1, adv2 = login(client, "advertiser1@geobid.local"), login(client, "advertiser2@geobid.local")
    admin = login(client, "admin@geobid.local")
    r = a.reserve_price

    before = client.get("/api/dashboard/poles/P014/analysis", headers=admin).json()
    assert before["status"] == "ACTIVE" and len(before["slots"]) == 12 and len(before["revenue_by_day"]) == 30
    assert "owner_name" not in before

    client.post(f"/api/auctions/{a.id}/bids", json={"amount": r}, headers=adv1)
    client.post(f"/api/auctions/{a.id}/bids", json={"amount": r + 300}, headers=adv2)

    mine = client.get("/api/dashboard/advertiser", headers=adv1).json()
    row = next(x for x in mine["my_auctions"] if x["id"] == a.id)
    assert row["my_bid"] == r and row["my_seat"] == 2 and row["my_seat_status"] == "LEADING"
    assert row["my_min_bid"] == r + 100 and row["seats_filled"] == 2
    assert mine["kpis"]["seats_held"] == 1 and mine["kpis"]["seats_at_risk"] == 1

    client.post(f"/api/auctions/{a.id}/complete", headers=admin)

    after = client.get("/api/dashboard/poles/P014/analysis", headers=admin).json()
    assert after["kpis"]["revenue_total"] - before["kpis"]["revenue_total"] == 2 * r + 300
    assert after["kpis"]["seats_sold"] - before["kpis"]["seats_sold"] == 2
    assert after["kpis"]["avg_seat_price"] == round((2 * r + 300) / 2)
    tomorrow = shift_svc.tomorrow().isoformat()
    assert next(p for p in after["revenue_by_day"] if p["date"] == tomorrow)["revenue"] == 2 * r + 300

    won = client.get("/api/dashboard/advertiser", headers=adv2).json()
    assert won["kpis"]["seats_won"] == 1 and won["kpis"]["total_spend"] == r + 300
    assert won["won"][0]["pole_code"] == "P014" and won["won"][0]["seat"] == 1


def test_dashboard_access_control(client, seeded, p014_auction):
    admin, adv = login(client, "admin@geobid.local"), login(client, "advertiser1@geobid.local")
    assert client.get("/api/dashboard/advertiser", headers=admin).status_code == 403
    assert client.get("/api/dashboard/owner", headers=admin).status_code == 404  # no pole owners
    assert client.get("/api/dashboard/admin", headers=admin).status_code == 404
    assert client.get("/api/dashboard/poles/P014/analysis", headers=admin).status_code == 200
    assert client.get("/api/dashboard/poles/P014/analysis", headers=adv).status_code == 403
    assert client.get("/api/dashboard/poles/P014/analysis").status_code == 401
    assert client.get("/api/dashboard/poles/P999/analysis", headers=admin).status_code == 404
    assert client.get("/api/users", headers=adv).status_code == 403


def test_opportunities_filters(client, seeded, p014_auction):
    rows = client.get("/api/dashboard/opportunities").json()
    assert [r["id"] for r in rows] == [p014_auction.id]
    assert rows[0]["next_min_bid"] == p014_auction.reserve_price and rows[0]["my_min_bid"] is None
    assert client.get("/api/dashboard/opportunities", params={"category": "LOW"}).json() == []
    assert client.get("/api/dashboard/opportunities", params={"max_price": p014_auction.reserve_price - 1}).json() == []
    assert client.get("/api/dashboard/opportunities", params={"round": "PREMIUM"}).json() == []
    far = {"latitude": 17.0, "longitude": 78.0, "radius_km": 5}
    assert client.get("/api/dashboard/opportunities", params=far).json() == []
    adv = login(client, "advertiser1@geobid.local")
    mine = client.get("/api/dashboard/opportunities", headers=adv).json()
    assert mine[0]["my_min_bid"] == p014_auction.reserve_price


def test_admin_users(client, seeded):
    admin = login(client, "admin@geobid.local")
    users = client.get("/api/users", params={"role": "ADVERTISER"}, headers=admin).json()
    assert len(users) == 9 and all(u["role"] == "ADVERTISER" for u in users)  # 8 demo advertisers + the fresh account


def test_dashboards_on_demo_data(client, db, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "synthetic_data_dir", tmp_path)
    seed_all(db, tmp_path, price_history=False)
    adv = client.get("/api/dashboard/advertiser", headers=login(client, "advertiser2@geobid.local")).json()
    assert adv["my_auctions"] and adv["kpis"]["open_auctions"] > 0
    ops = client.get("/api/dashboard/opportunities", params={"limit": 20}).json()
    assert len(ops) == 20 and ops[0]["slot_footfall"] >= ops[-1]["slot_footfall"]
    an = client.get("/api/dashboard/poles/P010/analysis", headers=login(client, "admin@geobid.local")).json()
    assert an["open_slots"] > 0 and an["kpis"]["revenue_total"] > 0 and all(s["avg_footfall"] > 0 and s["base_price"] > 0 for s in an["slots"])


def test_bid_history_outcomes(client, seeded, p014_auction):
    a, r = p014_auction, p014_auction.reserve_price
    adv1, adv2 = login(client, "advertiser1@geobid.local"), login(client, "advertiser2@geobid.local")
    client.post(f"/api/auctions/{a.id}/bids", json={"amount": r}, headers=adv1)
    client.post(f"/api/auctions/{a.id}/bids", json={"amount": r + 300}, headers=adv1)  # raises own bid
    client.post(f"/api/auctions/{a.id}/bids", json={"amount": r + 100}, headers=adv2)

    page = client.get("/api/dashboard/advertiser/bids", headers=adv1).json()
    assert page["total"] == 2
    newest, older = page["items"]
    assert newest["amount"] == r + 300 and newest["outcome"] == "HOLDING" and newest["seat"] == 1
    assert older["amount"] == r and older["outcome"] == "RAISED" and older["pole_code"] == "P014"

    client.post(f"/api/auctions/{a.id}/complete", headers=login(client, "admin@geobid.local"))
    newest = client.get("/api/dashboard/advertiser/bids", headers=adv1).json()["items"][0]
    assert newest["outcome"] == "WON" and newest["seat"] == 1
    assert client.get("/api/dashboard/advertiser/bids", params={"limit": 1, "offset": 1}, headers=adv1).json()["items"][0]["amount"] == r
    assert client.get("/api/dashboard/advertiser/bids").status_code == 401


def test_tariff_config_exposes_formula_inputs(client):
    cfg = client.get("/api/tariff/config").json()
    assert cfg["slot_footfall_exponent"] == settings.slot_footfall_exponent
    assert cfg["auction"]["premium_floor_multiplier"] == settings.premium_floor_multiplier
    assert cfg["auction"]["seats_per_slot"] == 4 and cfg["auction"]["min_increment"] == 100


def test_finance_dashboard(client, seeded, p014_auction):
    a, r = p014_auction, p014_auction.reserve_price
    admin = login(client, "admin@geobid.local")
    adv1, adv2 = login(client, "advertiser1@geobid.local"), login(client, "advertiser2@geobid.local")
    before = client.get("/api/dashboard/admin/finance", params={"days": 30, "granularity": "day"}, headers=admin).json()

    client.post(f"/api/auctions/{a.id}/bids", json={"amount": r}, headers=adv1)
    client.post(f"/api/auctions/{a.id}/bids", json={"amount": r + 300}, headers=adv2)
    client.post(f"/api/auctions/{a.id}/advance", headers=admin)  # qualifying closes: both seats confirmed
    client.post(f"/api/auctions/{a.id}/complete", headers=admin)

    # The slot is tomorrow, so it books into the window that ends tomorrow at the latest:
    # the finance window ends today, so check all-time totals and the per-advertiser figures.
    after = client.get("/api/dashboard/admin/finance", params={"days": 0, "granularity": "month"}, headers=admin).json()
    assert after["kpis"]["all_time_revenue"] - before["kpis"]["all_time_revenue"] == 0  # tomorrow isn't booked yet
    assert after["granularity"] == "month" and len(after["by_slot"]) == 12
    assert {c["category"] for c in after["by_category"]} == {"HIGH", "MEDIUM", "LOW"}
    assert client.get("/api/dashboard/admin/finance", headers=adv1).status_code == 403
    assert client.get("/api/dashboard/admin/finance", params={"granularity": "year"}, headers=admin).status_code == 422


def test_finance_dashboard_on_demo_data(client, db, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "synthetic_data_dir", tmp_path)
    seed_all(db, tmp_path, price_history=False)
    admin = login(client, "admin@geobid.local")
    d = client.get("/api/dashboard/admin/finance", params={"days": 90, "granularity": "week"}, headers=admin).json()
    k = d["kpis"]
    assert k["all_time_revenue"] > k["last_30_days"]["revenue"] > k["last_7_days"]["revenue"] > 0
    assert 0 < k["premium_share"] < 1 and 0 < k["seat_fill_rate"] <= 1 and k["active_buyers"] == 8  # the demo advertisers only
    assert sum(b["qualifying"] + b["premium"] for b in d["revenue"]) == sum(a["revenue"] for a in d["top_advertisers"]) or len(d["top_advertisers"]) == 10
    tops = [a["revenue"] for a in d["top_advertisers"]]
    assert tops == sorted(tops, reverse=True) and abs(sum(c["share"] for c in d["by_category"]) - 1) < 0.01
    freq = [(f["purchase_days"], f["seats"]) for f in d["frequent_buyers"]]
    assert freq == sorted(freq, reverse=True)
    poles = d["top_poles"]
    assert 0 < len(poles) <= 10 and poles[0]["revenue"] >= poles[-1]["revenue"] and 0 < poles[0]["fill_rate"] <= 1
    assert d["revenue"][0]["start"] <= d["window_start"]  # weeks start on Monday
    monthly = client.get("/api/dashboard/admin/finance", params={"days": 0, "granularity": "month"}, headers=admin).json()
    assert len(monthly["revenue"]) >= 6  # six months of history


def test_demo_data_is_consistent_and_realistic(client, db, tmp_path, monkeypatch):
    """Admin totals come from the same advertisers the dashboards show, at believable volumes."""
    monkeypatch.setattr(settings, "synthetic_data_dir", tmp_path)
    seed_all(db, tmp_path, price_history=False)
    admin = login(client, "admin@geobid.local")
    fin = client.get("/api/dashboard/admin/finance", params={"days": 0}, headers=admin).json()
    spends = {}
    for i in range(1, 9):
        d = client.get("/api/dashboard/advertiser", headers=login(client, f"advertiser{i}@geobid.local")).json()
        spends[i] = d["kpis"]["total_spend"]
        assert 0 < d["my_auctions_total"] <= 40 and d["kpis"]["seats_won"] < 2 * 180  # < 2 seats a day
        measured = []
        for won in d["won"]:
            assert won["predicted_footfall"] > 0
            assert won["predicted_low"] < won["predicted_footfall"] < won["predicted_high"]
            if won["actual_footfall"] is not None:  # slot has run: measured count close to the forecast
                assert abs(won["actual_footfall"] / won["predicted_footfall"] - 1) <= 0.16 + 0.01
                measured.append(won["predicted_low"] <= won["actual_footfall"] <= won["predicted_high"])
        assert measured and 0.6 <= sum(measured) / len(measured) < 1  # mostly right, sometimes a small miss
    assert sum(spends.values()) == fin["kpis"]["all_time_revenue"]  # nobody else is buying

    fresh = login(client, "newuser@geobid.local")
    d = client.get("/api/dashboard/advertiser", headers=fresh).json()
    assert d["my_auctions_total"] == 0 and d["kpis"]["seats_won"] == 0 and d["kpis"]["total_spend"] == 0
    assert client.get("/api/dashboard/advertiser/bids", headers=fresh).json()["total"] == 0


def test_signup_then_use_the_app(client, seeded):
    res = client.post("/api/auth/register", json={"name": "Test Brand", "email": "test.brand@example.com", "password": "secret123"})
    assert res.status_code == 201 and res.json()["user"]["role"] == "ADVERTISER"
    headers = {"Authorization": f"Bearer {res.json()['access_token']}"}
    assert client.get("/api/dashboard/advertiser", headers=headers).json()["my_auctions_total"] == 0
    again = client.post("/api/auth/register", json={"name": "Other", "email": "TEST.brand@example.com", "password": "secret123"})
    assert again.status_code == 409  # emails are unique, case-insensitively
    assert client.post("/api/auth/register", json={"name": "X", "email": "bad", "password": "short"}).status_code == 422


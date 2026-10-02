from datetime import date, datetime, timedelta, timezone

import pytest

from app.core.config import ShiftConfig, settings
from app.core.exceptions import NotFoundError
from app.models import InventorySlot, Pole, UserRole
from app.services import inventory_service, tariff_service
from app.services import shifts as shift_svc
from scripts.seed_database import seed_all


@pytest.fixture
def seeded(db, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "synthetic_data_dir", tmp_path)
    seed_all(db, tmp_path, demo_auctions=False, price_history=False)
    return db


# --- tariff engine --------------------------------------------------------------


def test_pole_value_weights():
    assert tariff_service.pole_value(100, 0) == 70.0
    assert tariff_service.pole_value(0, 100) == 30.0
    assert tariff_service.pole_value(90, 80) == 87.0


def test_pole_multiplier_range():
    assert tariff_service.pole_multiplier(0) == settings.pole_multiplier_min
    assert tariff_service.pole_multiplier(100) == settings.pole_multiplier_max


def test_quote_matches_formula():
    q = tariff_service.quote(90, 80, "S9")  # 16:00-18:00, VERY_HIGH
    value = 0.7 * 90 + 0.3 * 80
    mult = 0.5 + 1.5 * value / 100
    assert q.pole_value == value
    assert q.base_tariff == round(settings.base_tariff_inr * mult)
    assert q.shift_multiplier == 1.6
    assert q.reserve_price == round(q.base_tariff * 1.6 / 100) * 100
    assert q.reserve_price % settings.reserve_rounding_inr == 0


def test_demand_table_fallback_orders_prices():
    """Without a footfall profile, the configured shift demand prices the slot."""
    prices = {s.code: tariff_service.quote(80, 70, s.code).reserve_price for s in shift_svc.list_shifts()}
    # VERY_HIGH (16-20) > HIGH (08-10, 20-22) > MEDIUM (10-16) > LOW_MEDIUM > LOW (night)
    assert prices["S9"] == prices["S10"] > prices["S5"] == prices["S11"] > prices["S6"] == prices["S8"]
    assert prices["S6"] > prices["S4"] == prices["S12"] > prices["S1"] == prices["S3"]


def test_higher_scores_raise_tariff():
    assert tariff_service.quote(95, 90, "S4").reserve_price > tariff_service.quote(40, 50, "S4").reserve_price
    assert tariff_service.quote(70, 95, "S4").reserve_price > tariff_service.quote(70, 40, "S4").reserve_price


def test_tariff_is_configurable(monkeypatch):
    before = tariff_service.quote(80, 80, "S4").reserve_price
    monkeypatch.setattr(settings, "base_tariff_inr", settings.base_tariff_inr * 2)
    assert tariff_service.quote(80, 80, "S4").reserve_price == pytest.approx(before * 2, abs=100)


def test_unknown_shift_rejected():
    with pytest.raises(NotFoundError):
        tariff_service.quote(50, 50, "S13")


# --- shifts ---------------------------------------------------------------------


def test_default_twelve_two_hour_shifts_cover_the_day():
    shifts = shift_svc.list_shifts()
    assert [s.code for s in shifts] == [f"S{i}" for i in range(1, 13)]
    assert shifts[8].label == "16:00–18:00"
    windows = [shift_svc.shift_window(date(2026, 10, 3), s.code) for s in shifts]
    assert sum((end - start for start, end in windows), timedelta()) == timedelta(hours=24)
    # contiguous: each shift starts when the previous one ends
    assert all(windows[i][1] == windows[i + 1][0] for i in range(len(windows) - 1))
    assert all(end - start == timedelta(hours=2) for start, end in windows)


def test_shift_window_is_ist_and_crosses_midnight():
    start, end = shift_svc.shift_window(date(2026, 10, 3), "S12")
    assert start == datetime(2026, 10, 3, 16, 30, tzinfo=timezone.utc)  # 22:00 IST
    assert end == datetime(2026, 10, 3, 18, 30, tzinfo=timezone.utc)  # 00:00 IST next day


def test_shifts_are_configurable(monkeypatch, seeded):
    monkeypatch.setattr(
        settings,
        "shifts",
        [ShiftConfig(code="AM", start="06:00", end="18:00", demand="HIGH"),
         ShiftConfig(code="PM", start="18:00", end="06:00", demand="LOW")],
    )
    day = shift_svc.local_today() + timedelta(days=5)
    created = inventory_service.ensure_inventory(seeded, day)
    assert created == 2 * seeded.query(Pole).count()


# --- inventory ------------------------------------------------------------------


def test_seed_creates_twelve_slots_per_pole_for_next_two_days(seeded):
    n_poles = seeded.query(Pole).count()
    for ahead in (1, 2):
        day = shift_svc.local_today() + timedelta(days=ahead)
        slots = seeded.query(InventorySlot).filter_by(date=day).all()
        assert len(slots) == 12 * n_poles
        assert all(s.status.value == "AVAILABLE" and s.reserve_price > 0 for s in slots)


def test_ensure_inventory_is_idempotent(seeded):
    assert inventory_service.ensure_inventory(seeded, shift_svc.tomorrow()) == 0


def test_pole_inventory_endpoint(client, seeded):
    body = client.get("/api/poles/P014/inventory").json()
    assert body["pole_code"] == "P014"
    assert body["is_tomorrow"] is True
    assert body["market_status"] == "AVAILABLE"
    assert [s["shift"] for s in body["slots"]] == [f"S{i}" for i in range(1, 13)]
    slots = body["slots"]
    assert slots[8]["shift_label"] == "16:00–18:00"
    for s in slots:
        assert s["reserve_price"] == s["tariff"]["reserve_price"]
        assert s["tariff"]["basis"] == "slot_footfall" and s["tariff"]["slot_footfall"] == s["slot_footfall"]
    # priced by footfall: the busiest slot is the most expensive; prices rise with footfall
    busiest = max(slots, key=lambda s: s["slot_footfall"])
    assert busiest["reserve_price"] == max(s["reserve_price"] for s in slots)
    ordered = sorted(slots, key=lambda s: s["slot_footfall"])
    assert all(a["reserve_price"] <= b["reserve_price"] for a, b in zip(ordered, ordered[1:]))


def test_pole_inventory_other_date_empty(client, seeded):
    far = (shift_svc.local_today() + timedelta(days=30)).isoformat()
    body = client.get(f"/api/poles/P014/inventory?date={far}").json()
    assert body["slots"] == [] and body["market_status"] == "NO_INVENTORY"


def test_inventory_filters(client, seeded):
    rows = client.get("/api/inventory", params={"shift": "S5", "date": shift_svc.tomorrow().isoformat()}).json()
    assert len(rows) == seeded.query(Pole).count()
    assert all(r["shift"] == "S5" for r in rows)
    one = client.get(f"/api/inventory/{rows[0]['id']}").json()
    assert one["id"] == rows[0]["id"]


def test_admin_creates_inventory(client, seeded, auth_headers):
    admin = auth_headers("root@example.com", UserRole.ADMIN)
    pole_id = client.get("/api/poles/P014").json()["id"]
    day = (shift_svc.local_today() + timedelta(days=10)).isoformat()

    res = client.post("/api/inventory", json={"pole_id": pole_id, "date": day, "shift": "S5"}, headers=admin)
    assert res.status_code == 201, res.text
    assert res.json()["reserve_price"] == res.json()["tariff"]["reserve_price"]

    dup = client.post("/api/inventory", json={"pole_id": pole_id, "date": day, "shift": "S5"}, headers=admin)
    assert dup.status_code == 409

    override = client.post(
        "/api/inventory", json={"pole_id": pole_id, "date": day, "shift": "S4", "reserve_price": 12345}, headers=admin
    )
    assert override.json()["reserve_price"] == 12345


def test_inventory_validation(client, seeded, auth_headers):
    admin = auth_headers("root@example.com", UserRole.ADMIN)
    pole_id = client.get("/api/poles/P014").json()["id"]
    today = shift_svc.local_today().isoformat()
    future = (shift_svc.local_today() + timedelta(days=3)).isoformat()
    assert client.post("/api/inventory", json={"pole_id": pole_id, "date": today, "shift": "S5"}, headers=admin).status_code == 422
    assert client.post("/api/inventory", json={"pole_id": pole_id, "date": future, "shift": "S13"}, headers=admin).status_code == 404
    adv = auth_headers("adv@example.com")
    assert client.post("/api/inventory", json={"pole_id": pole_id, "date": future, "shift": "S5"}, headers=adv).status_code == 403


def test_tariff_config_endpoint(client):
    body = client.get("/api/tariff/config").json()
    assert len(body["shifts"]) == 12
    assert body["demand_multipliers"]["VERY_HIGH"] == 1.6
    assert "not an industry" in body["note"]


# --- footfall-based slot pricing ---------------------------------------------------


def test_slot_multiplier_math():
    assert tariff_service.slot_multiplier(100, 100) == 1.0
    assert tariff_service.slot_multiplier(200, 100) == pytest.approx(2 ** 0.6, abs=0.001)
    assert tariff_service.slot_multiplier(1, 100) == settings.slot_multiplier_min  # clamped
    assert tariff_service.slot_multiplier(10_000, 100) == settings.slot_multiplier_max


def test_demand_bands_from_footfall_ratio():
    assert [tariff_service.demand_level(r) for r in (0.2, 0.6, 1.0, 1.4, 2.0)] == [
        "LOW", "LOW_MEDIUM", "MEDIUM", "HIGH", "VERY_HIGH",
    ]


def test_quote_by_slot_footfall():
    daily = 8_400  # avg 2h slot = 700
    q = tariff_service.quote(80, 70, "S9", slot_footfall=1_400, daily_footfall=daily)
    assert q.basis == "slot_footfall" and q.avg_slot_footfall == 700
    assert q.shift_multiplier == pytest.approx(2 ** 0.6, abs=0.001)
    assert q.demand == "VERY_HIGH"
    assert q.reserve_price == round(q.base_tariff * q.shift_multiplier / 100) * 100
    quiet = tariff_service.quote(80, 70, "S9", slot_footfall=350, daily_footfall=daily)
    assert quiet.reserve_price < q.reserve_price and quiet.demand == "LOW_MEDIUM"


def test_same_slot_priced_by_that_weekdays_footfall(seeded):
    """P014 is a business-corridor pole: weekday evenings are busier, so dearer."""
    from app.services import slot_footfall_service

    pole = seeded.query(Pole).filter_by(code="P014").one()
    profile = slot_footfall_service.load_profiles(seeded, [pole.id])[pole.id]
    today = shift_svc.local_today()
    wednesday = next(today + timedelta(days=i) for i in range(1, 8) if (today + timedelta(days=i)).weekday() == 2)
    sunday = next(today + timedelta(days=i) for i in range(1, 8) if (today + timedelta(days=i)).weekday() == 6)
    wed = inventory_service.quote_slot(pole, wednesday, "S10", profile)
    sun = inventory_service.quote_slot(pole, sunday, "S10", profile)
    assert wed.slot_footfall > sun.slot_footfall and wed.reserve_price > sun.reserve_price


def test_no_profile_falls_back_to_demand_table(seeded):
    pole = seeded.query(Pole).filter_by(code="P014").one()
    q = inventory_service.quote_slot(pole, shift_svc.tomorrow(), "S9", None)
    assert q.basis == "demand_table" and q.shift_multiplier == settings.demand_multipliers["VERY_HIGH"]

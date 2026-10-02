from collections import defaultdict
from datetime import date, timedelta

import pytest

from app.core.config import settings
from app.footfall import SyntheticFootfallProvider
from app.models import Pole, PoleFootfallProfile
from app.services import slot_footfall_service
from app.services import shifts as shift_svc
from app.synthetic.generator import generate_dataset, write_dataset
from app.synthetic.hourly_profile import business_weight
from scripts.seed_database import seed_all


@pytest.fixture
def seeded(db, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "synthetic_data_dir", tmp_path)
    seed_all(db, tmp_path, demo_auctions=False, price_history=False)
    return db


def test_hourly_profile_matches_daily_footfall():
    ds = generate_dataset(seed=42)
    daily = {f.pole_code: f.footfall for f in ds.footfall}
    totals = defaultdict(int)
    for r in ds.hourly:
        totals[r.pole_code] += r.footfall
    assert len(ds.hourly) == len(ds.poles) * 7 * 24
    for code, total in totals.items():
        assert total / 7 == pytest.approx(daily[code], rel=0.002)


def test_profile_has_realistic_shape():
    ds = generate_dataset(seed=42)
    poles = {p.code: p for p in ds.poles}
    by = defaultdict(dict)
    for r in ds.hourly:
        by[r.pole_code][(r.weekday, r.hour)] = r.footfall
    for code, prof in by.items():
        night = prof[(2, 3)]
        evening = prof[(2, 18)]
        assert evening > 5 * night  # 18:00 much busier than 03:00
    # business corridors are weekday-heavy, residential areas weekend-heavy
    biz = max(poles.values(), key=lambda p: business_weight(p.latitude, p.longitude))
    res = min(poles.values(), key=lambda p: business_weight(p.latitude, p.longitude))
    day_total = lambda code, wd: sum(v for (d, _), v in by[code].items() if d == wd)  # noqa: E731
    assert day_total(biz.code, 2) > day_total(biz.code, 6)  # Wed > Sun
    assert day_total(res.code, 5) > day_total(res.code, 1)  # Sat > Tue


def test_provider_reads_hourly_profiles(tmp_path):
    write_dataset(generate_dataset(seed=42), tmp_path)
    profiles = SyntheticFootfallProvider(tmp_path).get_hourly_profiles(["P014", "NOPE"])
    assert set(profiles) == {"P014"} and len(profiles["P014"]) == 168


def test_refresh_stores_profiles(seeded):
    assert seeded.query(PoleFootfallProfile).count() == seeded.query(Pole).count() * 168


def test_shift_footfall_sums_hours_and_wraps_midnight():
    profile = {(wd, h): (wd + 1) * 100 + h for wd in range(7) for h in range(24)}
    monday = date(2026, 10, 5)
    assert monday.weekday() == 0
    # S9 = 16:00-18:00 -> hours 16 and 17 of Monday
    assert slot_footfall_service.shift_footfall(profile, monday, "S9") == (116) + (117)
    # S12 = 22:00-00:00 -> hours 22 and 23 of the same day
    assert slot_footfall_service.shift_footfall(profile, monday, "S12") == 122 + 123
    assert slot_footfall_service.shift_footfall(None, monday, "S9") is None


def test_slot_footfall_on_inventory_and_profile_api(client, seeded):
    tomorrow = shift_svc.tomorrow()
    inv = client.get("/api/poles/P014/inventory").json()
    by_shift = {s["shift"]: s["slot_footfall"] for s in inv["slots"]}
    assert all(v is not None and v >= 0 for v in by_shift.values())

    prof = client.get("/api/poles/P014/footfall-profile").json()
    assert prof["date"] == tomorrow.isoformat()
    assert [s["shift"] for s in prof["slots"]] == [f"S{i}" for i in range(1, 13)]
    assert {s["shift"]: s["footfall"] for s in prof["slots"]} == by_shift  # same numbers everywhere
    assert prof["daily_total"] == sum(by_shift.values())
    assert sum(s["share"] for s in prof["slots"]) == pytest.approx(1, abs=0.01)
    assert prof["peak_shift"] == max(by_shift, key=by_shift.get)
    assert [w["weekday"] for w in prof["by_weekday"]] == ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

    other = (tomorrow + timedelta(days=1)).isoformat()
    other_prof = client.get(f"/api/poles/P014/footfall-profile?date={other}").json()
    assert other_prof["weekday"] != prof["weekday"]

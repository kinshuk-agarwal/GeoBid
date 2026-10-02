import pytest

from app.core.config import settings
from app.footfall import FootfallProvider, FootfallReading, SyntheticFootfallProvider
from app.models import FootfallCategory, Pole, UserRole
from app.services import footfall_service
from app.services.footfall_ranking import classify_footfall
from app.synthetic.generator import footfall_to_score, generate_dataset, write_dataset
from app.utils.geo import haversine_km
from scripts.seed_database import seed_all

KONDAPUR = (settings.default_latitude, settings.default_longitude)


@pytest.fixture
def seeded(db, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "synthetic_data_dir", tmp_path)
    seed_all(db, tmp_path, demo_auctions=False, price_history=False)
    return db


# --- generation ---------------------------------------------------------------


def test_generator_sizes_and_bounds():
    ds = generate_dataset(seed=42)
    assert 10 <= len(ds.roads) <= 20
    assert 40 <= len(ds.poles) <= 80
    assert len({p.code for p in ds.poles}) == len(ds.poles)
    assert {f.pole_code for f in ds.footfall} == {p.code for p in ds.poles}
    for p in ds.poles:
        assert haversine_km(*KONDAPUR, p.latitude, p.longitude) <= 15
    for f in ds.footfall:
        assert f.footfall > 0
        assert 0 <= f.footfall_score <= 100
        assert 0 <= f.visibility_score <= 100


def test_generator_is_deterministic_per_seed():
    a, b, c = generate_dataset(seed=1), generate_dataset(seed=1), generate_dataset(seed=2)
    assert [f.footfall for f in a.footfall] == [f.footfall for f in b.footfall]
    assert [f.footfall for f in a.footfall] != [f.footfall for f in c.footfall]


def test_footfall_has_meaningful_spread():
    values = sorted(f.footfall for f in generate_dataset(seed=42).footfall)
    assert values[-1] / values[0] > 2.5


def test_score_is_monotonic_in_footfall():
    scores = [footfall_to_score(v) for v in range(500, 15_000, 250)]
    assert scores == sorted(scores)


def test_synthetic_provider_reads_model_output(tmp_path):
    ds = generate_dataset(seed=42)
    write_dataset(ds, tmp_path)
    provider = SyntheticFootfallProvider(tmp_path)
    readings = provider.get_readings(["P001", "P002", "NOPE"])
    assert set(readings) == {"P001", "P002"}
    assert readings["P001"].footfall == ds.footfall[0].footfall
    assert provider.info()["synthetic"] is True


def test_provider_missing_file_is_clear_error(tmp_path):
    with pytest.raises(FileNotFoundError, match="generate_synthetic_data"):
        SyntheticFootfallProvider(tmp_path).get_readings(["P001"])


# --- classification & ranking ----------------------------------------------------


def test_classification_uses_relative_shares():
    data = {i: 1000 * i for i in range(1, 21)}  # 20 poles
    ranks = classify_footfall(data, high_share=0.25, medium_share=0.40)
    cats = [ranks[i].category for i in sorted(data, key=lambda i: -data[i])]
    assert cats.count(FootfallCategory.HIGH) == 5
    assert cats.count(FootfallCategory.MEDIUM) == 8
    assert cats.count(FootfallCategory.LOW) == 7
    assert cats == sorted(cats, key=[FootfallCategory.HIGH, FootfallCategory.MEDIUM, FootfallCategory.LOW].index)
    assert ranks[20].rank == 1 and ranks[20].category_rank == 1
    assert ranks[15].category == FootfallCategory.MEDIUM and ranks[15].category_rank == 1


def test_classification_is_scale_free():
    """Same ordering at a different scale yields the same categories (no fixed thresholds)."""
    small = classify_footfall({i: i for i in range(1, 11)}, 0.3, 0.4)
    large = classify_footfall({i: i * 100_000 for i in range(1, 11)}, 0.3, 0.4)
    assert {k: v.category for k, v in small.items()} == {k: v.category for k, v in large.items()}


def test_classification_shares_are_configurable():
    data = {i: i for i in range(1, 11)}
    assert sum(r.category == FootfallCategory.HIGH for r in classify_footfall(data, 0.1, 0.4).values()) == 1
    assert sum(r.category == FootfallCategory.HIGH for r in classify_footfall(data, 0.5, 0.4).values()) == 5


def test_ties_share_category_and_rank():
    ranks = classify_footfall({1: 500, 2: 500, 3: 100, 4: 50}, high_share=0.25, medium_share=0.25)
    assert ranks[1].category == ranks[2].category == FootfallCategory.HIGH
    assert ranks[1].rank == ranks[2].rank == 1


def test_invalid_shares_rejected():
    with pytest.raises(ValueError):
        classify_footfall({1: 1}, 0.7, 0.5)


def test_classification_empty():
    assert classify_footfall({}, 0.25, 0.4) == {}


# --- database integration -------------------------------------------------------


def test_seed_assigns_categories_and_owners(seeded):
    poles = seeded.query(Pole).all()
    assert 40 <= len(poles) <= 80
    assert all(p.owner_id is not None and p.road_id is not None for p in poles)
    assert all(p.footfall_source == "synthetic" for p in poles)
    by_cat = {c: [p.footfall for p in poles if p.category == c] for c in FootfallCategory}
    assert min(by_cat[FootfallCategory.HIGH]) >= max(by_cat[FootfallCategory.MEDIUM])
    assert min(by_cat[FootfallCategory.MEDIUM]) >= max(by_cat[FootfallCategory.LOW])


class _FixedProvider(FootfallProvider):
    source_name = "test-model"

    def __init__(self, values: dict[str, int]):
        self.values = values

    def get_readings(self, pole_codes):
        return {
            c: FootfallReading(c, self.values[c], 50, 50) for c in pole_codes if c in self.values
        }


def test_swapping_provider_recomputes_categories(seeded):
    poles = seeded.query(Pole).order_by(Pole.footfall).all()
    lowest = poles[0]
    assert lowest.category == FootfallCategory.LOW

    result = footfall_service.refresh_from_provider(seeded, _FixedProvider({lowest.code: 999_999}))
    seeded.refresh(lowest)
    assert lowest.category == FootfallCategory.HIGH
    assert lowest.footfall_source == "test-model"
    assert result.updated == 1 and len(result.missing) == len(poles) - 1


# --- API ------------------------------------------------------------------------


def test_list_poles_sorted_with_ranks(client, seeded):
    body = client.get("/api/poles").json()
    assert [p["footfall"] for p in body] == sorted((p["footfall"] for p in body), reverse=True)
    assert body[0]["rank"] == 1 and body[0]["category"] == "HIGH"


def test_list_poles_filters(client, seeded):
    high = client.get("/api/poles", params={"category": "HIGH"}).json()
    assert high and all(p["category"] == "HIGH" for p in high)
    rich = client.get("/api/poles", params={"min_footfall": 9000}).json()
    assert all(p["footfall"] >= 9000 for p in rich)


def test_get_pole_by_code_and_id(client, seeded):
    by_code = client.get("/api/poles/p014").json()
    assert by_code["code"] == "P014"
    assert client.get(f"/api/poles/{by_code['id']}").json()["code"] == "P014"
    assert client.get("/api/poles/P999").status_code == 404


def test_map_radius_filters_and_top_lists(client, seeded):
    small = client.get("/api/map/poles", params={"radius_km": 5}).json()
    large = client.get("/api/map/poles", params={"radius_km": 15}).json()
    assert 0 < small["counts"]["total"] < large["counts"]["total"]
    assert all(p["distance_km"] <= 5 for p in small["poles"])
    assert small["roads"] and all(r["path"] for r in small["roads"])
    assert "Synthetic" in small["notice"]["footfall"]

    top_high = large["top"]["HIGH"]
    assert 0 < len(top_high) <= 5
    assert [p["footfall"] for p in top_high] == sorted((p["footfall"] for p in top_high), reverse=True)


def test_map_categories_do_not_change_with_radius(client, seeded):
    small = {p["code"]: p["category"] for p in client.get("/api/map/poles?radius_km=5").json()["poles"]}
    large = {p["code"]: p["category"] for p in client.get("/api/map/poles?radius_km=15").json()["poles"]}
    assert all(large[c] == cat for c, cat in small.items())


def test_nearby_sorted_by_distance(client, seeded):
    lat, lng = KONDAPUR
    res = client.get("/api/map/poles/nearby", params={"latitude": lat, "longitude": lng, "radius_km": 3})
    d = [p["distance_km"] for p in res.json()]
    assert d and d == sorted(d)


def test_roads_endpoint(client, seeded):
    roads = client.get("/api/roads").json()
    assert 10 <= len(roads) <= 20
    assert sum(r["pole_count"] for r in roads) == seeded.query(Pole).count()


def test_footfall_source(client, seeded):
    body = client.get("/api/footfall/source").json()
    assert body["source"] == "synthetic" and body["synthetic"] is True
    assert body["high_share"] == settings.footfall_high_share


def test_pole_crud_requires_admin(client, seeded, auth_headers):
    payload = {"code": "P900", "name": "Test", "latitude": 17.46, "longitude": 78.36, "footfall": 50_000,
               "footfall_score": 99, "visibility_score": 90}
    adv = auth_headers("adv@example.com")
    assert client.post("/api/poles", json=payload, headers=adv).status_code == 403
    assert client.post("/api/poles", json=payload).status_code == 401


def test_admin_pole_crud_recomputes_category(client, seeded, auth_headers):
    admin = auth_headers("root@example.com", UserRole.ADMIN)
    payload = {"code": "P900", "name": "Test", "latitude": 17.46, "longitude": 78.36, "footfall": 50_000,
               "footfall_score": 99, "visibility_score": 90}
    created = client.post("/api/poles", json=payload, headers=admin)
    assert created.status_code == 201, created.text
    assert created.json()["category"] == "HIGH" and created.json()["rank"] == 1
    assert created.json()["footfall_source"] == "manual"
    assert client.post("/api/poles", json=payload, headers=admin).status_code == 409

    updated = client.put("/api/poles/P900", json={"footfall": 10}, headers=admin).json()
    assert updated["category"] == "LOW"

    assert client.delete("/api/poles/P900", headers=admin).status_code == 204
    assert client.get("/api/poles/P900").status_code == 404


def test_admin_create_without_footfall_uses_provider(client, seeded, auth_headers):
    admin = auth_headers("root@example.com", UserRole.ADMIN)
    payload = {"code": "P901", "name": "No reading", "latitude": 17.46, "longitude": 78.36}
    res = client.post("/api/poles", json=payload, headers=admin)
    assert res.status_code == 422
    assert "provider has no reading" in res.json()["detail"]


def test_assigning_non_owner_rejected(client, seeded, auth_headers, make_user):
    admin = auth_headers("root@example.com", UserRole.ADMIN)
    adv = make_user("notowner@example.com", UserRole.ADVERTISER)
    res = client.put("/api/poles/P001", json={"owner_id": adv.id}, headers=admin)
    assert res.status_code == 422

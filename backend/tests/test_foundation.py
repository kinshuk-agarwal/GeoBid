from datetime import datetime, timezone

from sqlalchemy import inspect

from app.core.database import engine
from app.models import User, UserRole


def test_health(client):
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_public_config_defaults_to_kondapur(client):
    body = client.get("/api/config").json()
    assert body["default_location"]["name"].startswith("Kondapur")
    assert body["default_radius_km"] == 10
    assert body["allowed_radii_km"] == [5, 10, 15]


def test_all_tables_created():
    tables = set(inspect(engine).get_table_names())
    assert {
        "users",
        "roads",
        "poles",
        "inventory_slots",
        "auctions",
        "bids",
        "advertisements",
        "winning_advertisements",
    } <= tables


def test_datetimes_round_trip_as_utc(db, make_user):
    make_user("tz@example.com")
    db.expire_all()
    user = db.query(User).filter_by(email="tz@example.com").one()
    assert user.created_at.tzinfo is not None
    assert user.created_at.utcoffset() == timezone.utc.utcoffset(datetime.now())


def test_register_login_me(client):
    res = client.post(
        "/api/auth/register",
        json={"name": "Ad Co", "email": "Ad@Example.com", "password": "password123", "role": "ADVERTISER"},
    )
    assert res.status_code == 201, res.text
    assert res.json()["user"]["email"] == "ad@example.com"

    res = client.post("/api/auth/login", json={"email": "ad@example.com", "password": "password123"})
    assert res.status_code == 200
    token = res.json()["access_token"]

    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["role"] == "ADVERTISER"


def test_duplicate_registration_rejected(client):
    payload = {"name": "Dup", "email": "dup@example.com", "password": "password123"}
    assert client.post("/api/auth/register", json=payload).status_code == 201
    assert client.post("/api/auth/register", json=payload).status_code == 409


def test_cannot_self_register_as_admin(client):
    res = client.post(
        "/api/auth/register",
        json={"name": "Evil", "email": "evil@example.com", "password": "password123", "role": "ADMIN"},
    )
    assert res.status_code == 422


def test_wrong_password_rejected(client, make_user):
    make_user("a@example.com")
    res = client.post("/api/auth/login", json={"email": "a@example.com", "password": "nope-nope"})
    assert res.status_code == 401


def test_login_with_seeded_demo_domain(client, db):
    from scripts.seed_database import DEMO_PASSWORD, seed_users

    seed_users(db)
    res = client.post("/api/auth/login", json={"email": "admin@geobid.local", "password": DEMO_PASSWORD})
    assert res.status_code == 200, res.text
    assert res.json()["user"]["role"] == "ADMIN"


def test_me_requires_valid_token(client):
    assert client.get("/api/auth/me").status_code == 401
    bad = client.get("/api/auth/me", headers={"Authorization": "Bearer not-a-jwt"})
    assert bad.status_code == 401


def test_role_dependency(client, auth_headers):
    from app.api.deps import AdminUser
    from fastapi import APIRouter

    router = APIRouter()

    @router.get("/api/_test/admin-only")
    def admin_only(user: AdminUser) -> dict:
        return {"ok": True}

    client.app.include_router(router)
    assert client.get("/api/_test/admin-only", headers=auth_headers("adv@example.com")).status_code == 403
    admin = auth_headers("root@example.com", UserRole.ADMIN)
    assert client.get("/api/_test/admin-only", headers=admin).status_code == 200

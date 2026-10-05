"""Seed the GeoBid database.

Usage (from ``backend/``):
    python -m scripts.seed_database --reset   # drop everything, reseed (recommended)
    python -m scripts.seed_database           # create missing tables, seed if empty

Steps: demo users -> roads & pole sites (from the generated geography files)
-> footfall via the configured FootfallProvider -> relative categories
-> inventory for the next two days -> demo two-round auctions (qualifying round,
premium round, and a week of history). The synthetic dataset is generated
first if it does not exist yet. Auction times follow the real schedule, so
re-run with --reset to refresh the demo state on a later day.
"""

import argparse
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SessionLocal, init_db, reset_db
from app.footfall import get_footfall_provider
from app.models import FootfallCategory, Pole, Road, User, UserRole
from app.services import footfall_service
from app.services.inventory_service import ensure_upcoming_inventory
from app.synthetic.price_history import backfill_price_history
from scripts.demo_auctions import seed_demo_auctions
from app.services.auth_service import create_user, get_user_by_email
from app.synthetic.generator import dataset_exists, generate_dataset, read_geography, write_dataset

DEMO_PASSWORD = "geobid123"

DEMO_USERS: list[tuple[str, str, UserRole]] = [
    ("GeoBid Admin", "admin@geobid.local", UserRole.ADMIN),
    ("Aurora Coffee", "advertiser1@geobid.local", UserRole.ADVERTISER),
    ("Nimbus Mobile", "advertiser2@geobid.local", UserRole.ADVERTISER),
    ("Zenith Realty", "advertiser3@geobid.local", UserRole.ADVERTISER),
    ("Metro Mart", "advertiser4@geobid.local", UserRole.ADVERTISER),
    ("Swift Fitness", "advertiser5@geobid.local", UserRole.ADVERTISER),
    ("Pixel Studios", "advertiser6@geobid.local", UserRole.ADVERTISER),
    ("Bluewave Bank", "advertiser7@geobid.local", UserRole.ADVERTISER),
    ("Spice Route", "advertiser8@geobid.local", UserRole.ADVERTISER),
    # A fresh account with no bids or purchases, for testing a first-time bidder.
    ("New Advertiser", "newuser@geobid.local", UserRole.ADVERTISER),
]


def seed_users(db: Session) -> list[User]:
    users = []
    for name, email, role in DEMO_USERS:
        user = get_user_by_email(db, email) or create_user(
            db, name=name, email=email, password=DEMO_PASSWORD, role=role
        )
        users.append(user)
    return users


def seed_geography(db: Session, data_dir: Path) -> tuple[int, int]:
    """Insert roads and poles."""
    roads, poles = read_geography(data_dir)
    road_by_name: dict[str, Road] = {}
    for r in roads:
        road = Road(
            name=r.name,
            latitude=r.latitude,
            longitude=r.longitude,
            importance_score=r.importance_score,
            path=r.path,
        )
        db.add(road)
        road_by_name[r.name] = road
    db.flush()

    for p in poles:
        db.add(
            Pole(
                code=p.code,
                name=p.name,
                road_id=road_by_name[p.road].id,
                latitude=p.latitude,
                longitude=p.longitude,
            )
        )
    db.commit()
    return len(roads), len(poles)


def seed_all(
    db: Session, data_dir: Path | None = None, demo_auctions: bool = True, price_history: bool = True
) -> dict:
    data_dir = data_dir or settings.synthetic_data_dir
    if not dataset_exists(data_dir):
        write_dataset(generate_dataset(settings.synthetic_seed), data_dir)

    users = seed_users(db)
    summary = {"users": len(users), "roads": 0, "poles": 0, "slots": 0, "live": 0, "completed": 0}
    if db.scalar(select(func.count(Pole.id))) == 0:
        summary["roads"], summary["poles"] = seed_geography(db, data_dir)
        footfall_service.refresh_from_provider(db, get_footfall_provider())
        summary["slots"] = ensure_upcoming_inventory(db)
        if demo_auctions:
            summary.update(seed_demo_auctions(db))
        if price_history:
            summary["price_history"] = backfill_price_history(db, days=settings.price_trend_days)
    else:
        summary["slots"] = ensure_upcoming_inventory(db)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--reset", action="store_true", help="drop and recreate all tables")
    parser.add_argument("--no-auctions", action="store_true", help="skip demo auctions and bids")
    args = parser.parse_args()

    reset_db() if args.reset else init_db()

    with SessionLocal() as db:
        summary = seed_all(db, demo_auctions=not args.no_auctions)
        cats = dict(db.execute(select(Pole.category, func.count()).group_by(Pole.category)).all())

    print(
        f"Seeded {summary['users']} users, {summary['roads']} roads, {summary['poles']} poles, "
        f"{summary['slots']} inventory slots"
    )
    print(f"  auctions: {summary['live']} live, {summary['completed']} completed")
    print(f"  price history: {summary.get('price_history', 0)} synthetic pole-shift-days back-filled")
    print("  categories: " + ", ".join(f"{c.value}={cats.get(c, 0)}" for c in FootfallCategory))
    print(f"\nDemo accounts (password: {DEMO_PASSWORD}):")
    for _name, email, role in DEMO_USERS:
        print(f"  {role.value:<11} {email}")


if __name__ == "__main__":
    main()

"""Synthetic back-fill of past winning prices (POC only).

Real history accrues as auctions complete; this fills the previous two months
so price trends and expected ranges have something to show. Prices follow
the slot's base price for that day (which already reflects the slot's
footfall on that weekday) with:

* a demand premium (busier slots draw more competition above base),
* a gentle upward drift over the period,
* noise, and a chance of going unsold (higher for low-demand slots).
"""

import math
import random
from datetime import date, timedelta

from sqlalchemy import insert, select
from sqlalchemy.orm import Session

from app.models import Pole, PoleStatus
from app.models.price_history import SlotPriceHistory
from app.services import shifts as shift_svc
from app.services import slot_footfall_service, tariff_service

DEMAND_PREMIUM = {"LOW": 1.02, "LOW_MEDIUM": 1.06, "MEDIUM": 1.10, "HIGH": 1.18, "VERY_HIGH": 1.28}
UNSOLD_PROB = {"LOW": 0.35, "LOW_MEDIUM": 0.20, "MEDIUM": 0.10, "HIGH": 0.05, "VERY_HIGH": 0.02}
DRIFT = 0.06  # prices ~6% lower at the start of the window than today


def backfill_price_history(db: Session, days: int = 60, end: date | None = None, seed: int = 11) -> int:
    """Insert synthetic rows for [end - days, end) where none exist. Returns rows added."""
    end = end or shift_svc.local_today()
    start = end - timedelta(days=days)
    existing = set(
        db.execute(
            select(SlotPriceHistory.pole_id, SlotPriceHistory.date, SlotPriceHistory.shift).where(
                SlotPriceHistory.date >= start, SlotPriceHistory.date < end
            )
        ).all()
    )
    shifts = shift_svc.list_shifts()
    poles = list(db.scalars(select(Pole).where(Pole.status == PoleStatus.ACTIVE).order_by(Pole.id)))
    profiles = slot_footfall_service.load_profiles(db, [p.id for p in poles])
    rows = []
    for pole in poles:
        rng = random.Random(seed * 100_003 + pole.id)
        for shift in shifts:
            for i in range(days):
                day = start + timedelta(days=i)
                if (pole.id, day, shift.code) in existing:
                    continue
                sf = slot_footfall_service.shift_footfall(profiles.get(pole.id), day, shift.code)
                q = tariff_service.quote(pole.footfall_score, pole.visibility_score, shift.code, sf, pole.footfall)
                base, demand = q.reserve_price, q.demand
                if rng.random() < UNSOLD_PROB[demand]:
                    rows.append(dict(pole_id=pole.id, date=day, shift=shift.code, base_price=base,
                                     clearing_price=None, bid_count=0, source="synthetic"))
                    continue
                factor = DEMAND_PREMIUM[demand] * (1 - DRIFT * (days - i) / days)
                factor *= rng.lognormvariate(0, 0.07)
                price = max(base, int(math.ceil(base * factor / 100) * 100))
                rows.append(dict(pole_id=pole.id, date=day, shift=shift.code, base_price=base,
                                 clearing_price=price, bid_count=rng.randint(1, 9), source="synthetic"))
    if rows:
        db.execute(insert(SlotPriceHistory), rows)
        db.commit()
    return len(rows)

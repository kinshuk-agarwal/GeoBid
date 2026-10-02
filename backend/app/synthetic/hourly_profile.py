"""Synthetic hour-of-day / day-of-week footfall profile for one pole.

Each pole blends two shapes according to how close it is to business hubs:

* business corridor (HITEC City, Gachibowli, Financial District): sharp
  weekday commute peaks (08-10, 17-20), quiet weekends;
* residential / retail (Kondapur, Madhapur, Miyapur, KPHB): a broad evening
  peak and busier weekends.

The profile is scaled so the average daily total equals the pole's daily
footfall from the model output, so the two always agree.
"""

import math
import random

from app.utils.geo import haversine_km

# (lat, lng, sigma_km) of business districts
BUSINESS_HUBS = [
    (17.4504, 78.3809, 1.6),  # Cyber Towers / HITEC City
    (17.4401, 78.3489, 1.3),  # Gachibowli Junction
    (17.4180, 78.3430, 1.6),  # Financial District
]

# Relative hourly weights, 00:00 ... 23:00.
BUSINESS_WEEKDAY = [0.3, 0.2, 0.2, 0.2, 0.3, 0.8, 2.0, 4.5, 7.5, 8.5, 6.0, 5.0,
                    5.5, 6.0, 4.5, 4.5, 5.5, 7.5, 8.5, 7.5, 5.5, 3.8, 2.2, 1.0]
RETAIL = [0.5, 0.3, 0.2, 0.2, 0.3, 0.7, 1.5, 2.5, 4.0, 4.5, 5.0, 5.5,
          6.0, 6.0, 5.5, 5.5, 6.5, 7.5, 8.5, 9.0, 8.0, 6.0, 3.5, 1.5]

# Day-of-week multipliers, Monday=0 ... Sunday=6.
BUSINESS_DAY = [1.12, 1.12, 1.12, 1.12, 1.10, 0.78, 0.62]
RETAIL_DAY = [0.93, 0.92, 0.93, 0.95, 1.02, 1.15, 1.12]


def business_weight(lat: float, lng: float) -> float:
    """0 = residential/retail, 1 = business corridor."""
    w = sum(math.exp(-((haversine_km(lat, lng, hl, hg) / s) ** 2)) for hl, hg, s in BUSINESS_HUBS)
    return min(w, 1.0)


def _norm(xs: list[float]) -> list[float]:
    t = sum(xs)
    return [x / t for x in xs]


def hourly_profile(lat: float, lng: float, daily_footfall: int, rng: random.Random) -> dict[tuple[int, int], int]:
    """Footfall per (weekday, hour) for one pole."""
    w = business_weight(lat, lng)
    biz, ret = _norm(BUSINESS_WEEKDAY), _norm(RETAIL)
    raw: dict[tuple[int, int], float] = {}
    for wd in range(7):
        weekend = wd >= 5
        # On weekends even business corridors follow the leisure pattern.
        shape = ret if weekend else [w * b + (1 - w) * r for b, r in zip(biz, ret)]
        day_mult = w * BUSINESS_DAY[wd] + (1 - w) * RETAIL_DAY[wd]
        for h in range(24):
            raw[(wd, h)] = shape[h] * day_mult * rng.lognormvariate(0, 0.06)
    # Scale so the mean daily total matches the model's daily footfall.
    scale = daily_footfall * 7 / sum(raw.values())
    return {k: max(0, round(v * scale)) for k, v in raw.items()}

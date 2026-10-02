"""Deterministic synthetic dataset generator.

Produces three artefacts:

* ``roads.json``                 – major roads (approximate geometry)
* ``poles.csv``                  – fictional pole sites along those roads
* ``footfall_model_output.csv``  – what an upstream footfall model would emit
                                   for each pole (footfall + scores)
* ``footfall_hourly_profile.csv`` – the model's footfall per pole, weekday and
                                   hour (sums to the daily figure on average)

The footfall values are a simple function of road importance, proximity to
commercial hubs and random noise. They are *not* a traffic model; they only
need to look like plausible model output with a realistic spread.
"""

import csv
import json
import math
import random
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from app.synthetic.geography import GEOGRAPHY_NOTICE, HUBS, ROADS
from app.synthetic.hourly_profile import hourly_profile
from app.utils.geo import haversine_km, point_along_polyline, polyline_length_km

MODEL_VERSION = "synthetic-footfall-v1"

ROADS_FILE = "roads.json"
POLES_FILE = "poles.csv"
FOOTFALL_FILE = "footfall_model_output.csv"
HOURLY_FILE = "footfall_hourly_profile.csv"
METADATA_FILE = "metadata.json"

# Footfall range used to normalise footfall_score (log scale).
_SCORE_FLOOR = 1_000
_SCORE_CEIL = 12_000


@dataclass
class RoadRecord:
    name: str
    importance_score: int
    latitude: float
    longitude: float
    path: list[list[float]]


@dataclass
class PoleRecord:
    code: str
    name: str
    road: str
    latitude: float
    longitude: float


@dataclass
class FootfallRecord:
    pole_code: str
    footfall: int
    footfall_score: int
    visibility_score: int


@dataclass
class HourlyRecord:
    pole_code: str
    weekday: int  # Monday=0
    hour: int  # 0-23, footfall during [hour, hour+1)
    footfall: int


@dataclass
class SyntheticDataset:
    seed: int
    roads: list[RoadRecord] = field(default_factory=list)
    poles: list[PoleRecord] = field(default_factory=list)
    footfall: list[FootfallRecord] = field(default_factory=list)
    hourly: list[HourlyRecord] = field(default_factory=list)
    generated_at: str = ""


def footfall_to_score(footfall: int) -> int:
    """Map footfall to 0-100 on a log scale (monotonic in footfall)."""
    lo, hi = math.log(_SCORE_FLOOR), math.log(_SCORE_CEIL)
    s = 100 * (math.log(max(footfall, 1)) - lo) / (hi - lo)
    return int(round(min(max(s, 5), 99)))


def _hub_effect(lat: float, lng: float) -> float:
    total = 0.0
    for _label, hlat, hlng, weight, sigma in HUBS:
        d = haversine_km(lat, lng, hlat, hlng)
        total += weight * math.exp(-((d / sigma) ** 2))
    return min(total, 1.3)


def _nearest_label(lat: float, lng: float, waypoints) -> str:
    return min(waypoints, key=lambda w: haversine_km(lat, lng, w[1], w[2]))[0]


def generate_dataset(seed: int = 42, spacing_km: float = 1.0) -> SyntheticDataset:
    rng = random.Random(seed)
    ds = SyntheticDataset(seed=seed, generated_at=datetime.now(timezone.utc).isoformat())

    pole_no = 0
    for road in ROADS:
        path = [[lat, lng] for _label, lat, lng in road["waypoints"]]
        length = polyline_length_km(path)
        mid = point_along_polyline(path, length / 2)
        ds.roads.append(
            RoadRecord(
                name=road["name"],
                importance_score=road["importance"],
                latitude=round(mid[0], 6),
                longitude=round(mid[1], 6),
                path=path,
            )
        )

        n_poles = max(2, round(length / spacing_km))
        step = length / n_poles
        for i in range(n_poles):
            pole_no += 1
            # Evenly spaced with some jitter along the road, plus a small
            # sideways offset so poles don't sit exactly on the centreline.
            dist = step * (i + 0.5) + rng.uniform(-0.2, 0.2) * step
            lat, lng = point_along_polyline(path, dist)
            lat += rng.uniform(-0.00012, 0.00012)
            lng += rng.uniform(-0.00012, 0.00012)
            code = f"P{pole_no:03d}"
            ds.poles.append(
                PoleRecord(
                    code=code,
                    name=f"Near {_nearest_label(lat, lng, road['waypoints'])}",
                    road=road["name"],
                    latitude=round(lat, 6),
                    longitude=round(lng, 6),
                )
            )

            importance = road["importance"] / 100
            hub = _hub_effect(lat, lng)
            base = 1_600 + 4_800 * importance**1.6 + 4_200 * hub
            footfall = int(round(base * rng.lognormvariate(0, 0.16), -1))
            footfall = min(max(footfall, 1_200), 13_500)

            near_junction = any(
                haversine_km(lat, lng, w[1], w[2]) < 0.35 for w in road["waypoints"]
            )
            visibility = 48 + 22 * rng.random() + 18 * importance + (8 if near_junction else 0)
            ds.footfall.append(
                FootfallRecord(
                    pole_code=code,
                    footfall=footfall,
                    footfall_score=footfall_to_score(footfall),
                    visibility_score=int(round(min(max(visibility, 35), 98))),
                )
            )
            # Separate stream so adding the profile doesn't shift other values.
            profile = hourly_profile(lat, lng, footfall, random.Random(seed * 1_000 + pole_no))
            ds.hourly.extend(HourlyRecord(code, wd, h, v) for (wd, h), v in sorted(profile.items()))

    return ds


def write_dataset(ds: SyntheticDataset, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)

    (out_dir / ROADS_FILE).write_text(
        json.dumps([asdict(r) for r in ds.roads], indent=2), encoding="utf-8"
    )

    with (out_dir / POLES_FILE).open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["pole_id", "name", "road", "latitude", "longitude"])
        for p in ds.poles:
            w.writerow([p.code, p.name, p.road, p.latitude, p.longitude])

    with (out_dir / FOOTFALL_FILE).open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["pole_id", "footfall", "footfall_score", "visibility_score", "model_version"])
        for r in ds.footfall:
            w.writerow([r.pole_code, r.footfall, r.footfall_score, r.visibility_score, MODEL_VERSION])

    with (out_dir / HOURLY_FILE).open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["pole_id", "weekday", "hour", "footfall", "model_version"])
        for r in ds.hourly:
            w.writerow([r.pole_code, r.weekday, r.hour, r.footfall, MODEL_VERSION])

    metadata = {
        "model_version": MODEL_VERSION,
        "seed": ds.seed,
        "generated_at": ds.generated_at,
        "roads": len(ds.roads),
        "poles": len(ds.poles),
        "footfall_notice": "Synthetic footfall data — POC. Not real measurements.",
        "geography_notice": GEOGRAPHY_NOTICE,
    }
    (out_dir / METADATA_FILE).write_text(json.dumps(metadata, indent=2), encoding="utf-8")


def read_geography(data_dir: Path) -> tuple[list[RoadRecord], list[PoleRecord]]:
    roads = [RoadRecord(**r) for r in json.loads((data_dir / ROADS_FILE).read_text(encoding="utf-8"))]
    with (data_dir / POLES_FILE).open(newline="", encoding="utf-8") as f:
        poles = [
            PoleRecord(
                code=row["pole_id"],
                name=row["name"],
                road=row["road"],
                latitude=float(row["latitude"]),
                longitude=float(row["longitude"]),
            )
            for row in csv.DictReader(f)
        ]
    return roads, poles


def dataset_exists(data_dir: Path) -> bool:
    return all((data_dir / f).exists() for f in (ROADS_FILE, POLES_FILE, FOOTFALL_FILE, HOURLY_FILE))

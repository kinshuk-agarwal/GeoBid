"""Small geodesic helpers (no external GIS dependency needed for a POC)."""

import math

EARTH_RADIUS_KM = 6371.0088


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def polyline_length_km(path: list[tuple[float, float]] | list[list[float]]) -> float:
    return sum(haversine_km(*path[i], *path[i + 1]) for i in range(len(path) - 1))


def point_along_polyline(path, distance_km: float) -> tuple[float, float]:
    """Linearly interpolate the point ``distance_km`` along ``path``."""
    remaining = distance_km
    for i in range(len(path) - 1):
        a, b = path[i], path[i + 1]
        seg = haversine_km(*a, *b)
        if remaining <= seg or i == len(path) - 2:
            t = 0.0 if seg == 0 else min(remaining / seg, 1.0)
            return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)
        remaining -= seg
    return tuple(path[-1])  # type: ignore[return-value]

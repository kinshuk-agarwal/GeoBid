"""Caching map-tile proxy.

Browsers fetch tiles from GeoBid instead of directly from OpenStreetMap. Each
tile is fetched upstream once, with an identifying User-Agent as the OSM tile
usage policy requires, and cached on disk. Remote devices (e.g. via port
forwarding, where the browser's Referer may be stripped) then never hit OSM
directly, and repeat views cost the volunteer-run servers nothing.
"""

import asyncio

import httpx
from fastapi import APIRouter, HTTPException, Path, Response

from app import __version__
from app.core.config import settings

router = APIRouter(tags=["map"])

_client: httpx.AsyncClient | None = None
_locks: dict[str, asyncio.Lock] = {}

CACHE_HEADERS = {"Cache-Control": "public, max-age=604800"}  # 7 days


def _http() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(
            timeout=10.0,
            headers={"User-Agent": f"GeoBid-POC/{__version__} (local proof of concept; tile cache)"},
        )
    return _client


@router.get("/tiles/{z}/{x}/{y}.png", include_in_schema=False)
async def tile(
    z: int = Path(ge=0, le=19),
    x: int = Path(ge=0),
    y: int = Path(ge=0),
) -> Response:
    n = 2**z
    if x >= n or y >= n:
        raise HTTPException(status_code=404, detail="Tile out of range")

    path = settings.tile_cache_dir / str(z) / str(x) / f"{y}.png"
    if path.exists():
        return Response(path.read_bytes(), media_type="image/png", headers=CACHE_HEADERS)

    key = f"{z}/{x}/{y}"
    lock = _locks.setdefault(key, asyncio.Lock())
    async with lock:  # one upstream fetch per tile, even under concurrent requests
        if not path.exists():
            url = settings.tile_upstream_url.format(z=z, x=x, y=y)
            try:
                res = await _http().get(url)
            except httpx.HTTPError as exc:
                raise HTTPException(status_code=502, detail=f"Tile server unreachable: {exc}") from exc
            if res.status_code != 200 or not res.headers.get("content-type", "").startswith("image/"):
                raise HTTPException(status_code=502, detail=f"Tile server returned {res.status_code}")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(res.content)
    _locks.pop(key, None)
    return Response(path.read_bytes(), media_type="image/png", headers=CACHE_HEADERS)

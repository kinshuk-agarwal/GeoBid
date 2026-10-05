"""Footfall camera videos: list them and stream one (with HTTP range support for seeking).

Serves the browser-playable copies in ``<videos_dir>/web/`` made by
``python -m scripts.prepare_videos``.
"""

import json
import re

from fastapi import APIRouter
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.core.config import settings
from app.core.exceptions import NotFoundError

router = APIRouter(tags=["videos"])

_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*\.mp4$")


class VideoOut(BaseModel):
    name: str
    title: str
    url: str  # relative to the API root, e.g. /api/videos/input.mp4
    size_bytes: int
    width: int | None = None
    height: int | None = None
    duration_s: float | None = None


def _web_dir():
    return settings.videos_dir / "web"


def list_videos() -> list[VideoOut]:
    web = _web_dir()
    if not web.is_dir():
        return []
    meta = {}
    index = web / "index.json"
    if index.exists():
        meta = {v["name"]: v for v in json.loads(index.read_text(encoding="utf-8"))}
    out = []
    for f in sorted(web.glob("*.mp4")):
        m = meta.get(f.name, {})
        out.append(
            VideoOut(
                name=f.name,
                title="",  # numbered below, in display order
                url=f"/api/videos/{f.name}",
                size_bytes=f.stat().st_size,
                width=m.get("width"),
                height=m.get("height"),
                duration_s=m.get("duration_s"),
            )
        )
    # Raw input first, then the annotated outputs; shown as "Video 1", "Video 2", ...
    out.sort(key=lambda v: (v.name != "input.mp4", v.name))
    for i, v in enumerate(out, start=1):
        v.title = f"Video {i}"
    return out


@router.get("/videos", response_model=list[VideoOut])
def videos() -> list[VideoOut]:
    """Footfall camera videos (raw input and annotated detection output)."""
    return list_videos()


@router.get("/videos/{name}", include_in_schema=False)
def video_file(name: str) -> FileResponse:
    path = _web_dir() / name
    if not _NAME.fullmatch(name) or not path.is_file():
        raise NotFoundError(f"Video {name} not found")
    # FileResponse answers Range requests, so the player can seek.
    return FileResponse(path, media_type="video/mp4", headers={"Cache-Control": "public, max-age=86400"})

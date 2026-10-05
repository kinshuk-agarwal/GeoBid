import json

import pytest

from app.core.config import settings


@pytest.fixture
def video_dir(tmp_path, monkeypatch):
    web = tmp_path / "web"
    web.mkdir()
    (web / "input.mp4").write_bytes(b"\x00" * 1000)
    (web / "annotated2.mp4").write_bytes(bytes(range(256)) * 4)
    (web / "index.json").write_text(json.dumps([{"name": "input.mp4", "width": 360, "height": 640, "duration_s": 10.1}]))
    (tmp_path / "secret.txt").write_text("nope")
    monkeypatch.setattr(settings, "videos_dir", tmp_path)
    return web


def test_list_videos(client, video_dir):
    vids = client.get("/api/videos").json()
    assert [v["name"] for v in vids] == ["input.mp4", "annotated2.mp4"]  # raw input first
    assert vids[0]["title"] == "Video 1" and vids[0]["duration_s"] == 10.1 and vids[0]["height"] == 640
    assert vids[1]["title"] == "Video 2" and vids[1]["duration_s"] is None
    assert vids[1]["url"] == "/api/videos/annotated2.mp4" and vids[1]["size_bytes"] == 1024


def test_stream_video_supports_ranges(client, video_dir):
    full = client.get("/api/videos/annotated2.mp4")
    assert full.status_code == 200 and full.headers["content-type"] == "video/mp4" and len(full.content) == 1024
    part = client.get("/api/videos/annotated2.mp4", headers={"Range": "bytes=256-511"})
    assert part.status_code == 206 and part.content == bytes(range(256))


def test_video_names_are_validated(client, video_dir):
    assert client.get("/api/videos/missing.mp4").status_code == 404
    assert client.get("/api/videos/..%2Fsecret.txt").status_code == 404
    assert client.get("/api/videos/index.json").status_code == 404


def test_no_videos_folder(client, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "videos_dir", tmp_path / "absent")
    assert client.get("/api/videos").json() == []


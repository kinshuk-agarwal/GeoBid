"""Make browser-playable copies of the footfall videos.

Videos written by OpenCV use MPEG-4 Part 2 (``mp4v``), which browsers don't
play. This converts every ``*.mp4`` in the videos folder to H.264 in
``<videos>/web/`` (originals are left untouched) and writes ``index.json``
with each video's duration and size for the ``/api/videos`` listing.

Usage (needs ffmpeg/ffprobe on PATH):
    python -m scripts.prepare_videos            # convert new/changed videos
    python -m scripts.prepare_videos --force    # re-convert everything
"""

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

from app.core.config import settings


def probe(path: Path) -> dict:
    out = subprocess.run(
        [
            "ffprobe", "-v", "error", "-select_streams", "v:0",
            "-show_entries", "stream=width,height:format=duration",
            "-of", "json", str(path),
        ],
        check=True, capture_output=True, text=True,
    ).stdout
    data = json.loads(out)
    stream = data["streams"][0]
    return {
        "width": int(stream["width"]),
        "height": int(stream["height"]),
        "duration_s": round(float(data["format"]["duration"]), 1),
    }


def convert(src: Path, dst: Path) -> None:
    subprocess.run(
        [
            "ffmpeg", "-y", "-v", "error", "-i", str(src),
            "-c:v", "libx264", "-preset", "medium", "-crf", "23",
            "-pix_fmt", "yuv420p",  # widest browser support
            "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2",  # H.264 needs even dimensions
            "-movflags", "+faststart",  # metadata first, so playback starts before download ends
            "-an", str(dst),
        ],
        check=True,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--force", action="store_true", help="re-convert videos that already have a web copy")
    args = parser.parse_args()

    if not (shutil.which("ffmpeg") and shutil.which("ffprobe")):
        print("ffmpeg and ffprobe must be on PATH", file=sys.stderr)
        return 1
    src_dir = settings.videos_dir
    web_dir = src_dir / "web"
    web_dir.mkdir(parents=True, exist_ok=True)

    index = []
    for src in sorted(src_dir.glob("*.mp4")):
        dst = web_dir / src.name
        if args.force or not dst.exists() or dst.stat().st_mtime < src.stat().st_mtime:
            print(f"converting {src.name} ...")
            convert(src, dst)
        index.append({"name": dst.name, "size_bytes": dst.stat().st_size, **probe(dst)})
        print(f"  {dst.name}: {index[-1]}")
    (web_dir / "index.json").write_text(json.dumps(index, indent=2), encoding="utf-8")
    print(f"{len(index)} videos ready in {web_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

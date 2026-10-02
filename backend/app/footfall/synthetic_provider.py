import csv
import json
from collections.abc import Iterable
from pathlib import Path

from app.footfall.provider import FootfallProvider, FootfallReading

FOOTFALL_FILE = "footfall_model_output.csv"
HOURLY_FILE = "footfall_hourly_profile.csv"
METADATA_FILE = "metadata.json"


class SyntheticFootfallProvider(FootfallProvider):
    """Reads the synthetic model-output file written by
    ``scripts/generate_synthetic_data.py``.

    It behaves like a consumer of an upstream model's batch output: it only
    reads the file, it does not know how the numbers were produced.
    """

    source_name = "synthetic"

    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        self._readings: dict[str, FootfallReading] | None = None

    def _load(self) -> dict[str, FootfallReading]:
        if self._readings is None:
            path = self.data_dir / FOOTFALL_FILE
            if not path.exists():
                raise FileNotFoundError(
                    f"{path} not found. Run `python -m scripts.generate_synthetic_data` first."
                )
            with path.open(newline="", encoding="utf-8") as f:
                self._readings = {
                    row["pole_id"]: FootfallReading(
                        pole_code=row["pole_id"],
                        footfall=int(row["footfall"]),
                        footfall_score=int(row["footfall_score"]),
                        visibility_score=int(row["visibility_score"]),
                    )
                    for row in csv.DictReader(f)
                }
        return self._readings

    def get_readings(self, pole_codes: Iterable[str]) -> dict[str, FootfallReading]:
        data = self._load()
        return {code: data[code] for code in pole_codes if code in data}

    def get_hourly_profiles(self, pole_codes: Iterable[str]) -> dict[str, dict[tuple[int, int], int]]:
        path = self.data_dir / HOURLY_FILE
        if not path.exists():
            return {}
        wanted = set(pole_codes)
        out: dict[str, dict[tuple[int, int], int]] = {}
        with path.open(newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                if row["pole_id"] in wanted:
                    out.setdefault(row["pole_id"], {})[(int(row["weekday"]), int(row["hour"]))] = int(row["footfall"])
        return out

    def info(self) -> dict:
        meta_path = self.data_dir / METADATA_FILE
        meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
        return {
            "source": self.source_name,
            "synthetic": True,
            "model_version": meta.get("model_version"),
            "generated_at": meta.get("generated_at"),
            "notice": "Synthetic footfall data — POC. Not real measurements.",
        }

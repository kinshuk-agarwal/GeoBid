"""Footfall provider abstraction.

GeoBid does not compute footfall. An upstream system (an ML model, an
external API, a computer-vision pipeline, ...) produces per-pole footfall and
scores; GeoBid consumes them through this interface. Swapping providers must
not require changes to ranking, tariff or auction code.
"""

from abc import ABC, abstractmethod
from collections.abc import Iterable
from dataclasses import dataclass


@dataclass(frozen=True)
class FootfallReading:
    pole_code: str
    footfall: int  # estimated daily footfall
    footfall_score: int  # 0-100, provider-normalised
    visibility_score: int  # 0-100


class FootfallProvider(ABC):
    #: short identifier stored on each pole as ``footfall_source``
    source_name: str

    @abstractmethod
    def get_readings(self, pole_codes: Iterable[str]) -> dict[str, FootfallReading]:
        """Return readings keyed by pole code. Unknown poles are omitted."""

    def get_hourly_profiles(self, pole_codes: Iterable[str]) -> dict[str, dict[tuple[int, int], int]]:
        """Footfall per (weekday Monday=0, hour 0-23), keyed by pole code.

        Optional: a provider without time-of-day output returns ``{}`` and
        GeoBid falls back to daily footfall only.
        """
        return {}

    def info(self) -> dict:
        return {"source": self.source_name, "synthetic": False}

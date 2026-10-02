"""Application configuration.

All settings can be overridden with environment variables prefixed with
``GEOBID_`` (e.g. ``GEOBID_DATABASE_URL``) or via a ``.env`` file at the
repository root or in ``backend/``.
"""

from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
REPO_DIR = BACKEND_DIR.parent


class ShiftConfig(BaseModel):
    """One daily advertising shift. ``end`` <= ``start`` means it ends next day."""

    code: str
    start: str  # "HH:MM", local time
    end: str
    demand: str  # key into Settings.demand_multipliers


# Twelve 2-hour shifts. Demand levels are POC pricing assumptions, not a
# traffic model.
DEFAULT_SHIFTS = [
    ShiftConfig(code="S1", start="00:00", end="02:00", demand="LOW"),
    ShiftConfig(code="S2", start="02:00", end="04:00", demand="LOW"),
    ShiftConfig(code="S3", start="04:00", end="06:00", demand="LOW"),
    ShiftConfig(code="S4", start="06:00", end="08:00", demand="LOW_MEDIUM"),
    ShiftConfig(code="S5", start="08:00", end="10:00", demand="HIGH"),
    ShiftConfig(code="S6", start="10:00", end="12:00", demand="MEDIUM"),
    ShiftConfig(code="S7", start="12:00", end="14:00", demand="MEDIUM"),
    ShiftConfig(code="S8", start="14:00", end="16:00", demand="MEDIUM"),
    ShiftConfig(code="S9", start="16:00", end="18:00", demand="VERY_HIGH"),
    ShiftConfig(code="S10", start="18:00", end="20:00", demand="VERY_HIGH"),
    ShiftConfig(code="S11", start="20:00", end="22:00", demand="HIGH"),
    ShiftConfig(code="S12", start="22:00", end="00:00", demand="LOW_MEDIUM"),
]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="GEOBID_",
        env_file=(REPO_DIR / ".env", BACKEND_DIR / ".env"),
        extra="ignore",
    )

    app_name: str = "GeoBid"
    environment: str = "development"

    database_url: str = f"sqlite:///{(BACKEND_DIR / 'geobid.db').as_posix()}"

    jwt_secret: str = "geobid-poc-dev-secret-change-me-0123456789abcdef"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 12
    bcrypt_rounds: int = 12

    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    # Also allow origins matching this regex, e.g. "https://.*\.vercel\.app"
    # for Vercel production and preview deployments.
    cors_origin_regex: str | None = None

    # Default map view: Kondapur, Hyderabad.
    default_location_name: str = "Kondapur, Hyderabad"
    default_latitude: float = 17.4615
    default_longitude: float = 78.3640
    default_radius_km: float = 10.0
    allowed_radii_km: list[float] = [5.0, 10.0, 15.0]

    # Footfall provider. Only "synthetic" exists in the POC; a real upstream
    # model would be plugged in as another provider (see app/footfall).
    footfall_provider: str = "synthetic"
    synthetic_data_dir: Path = BACKEND_DIR / "data" / "generated"

    # Map tiles are proxied and cached by the backend (see app/api/tiles.py).
    tile_upstream_url: str = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
    tile_cache_dir: Path = BACKEND_DIR / "data" / "tile_cache"
    synthetic_seed: int = 42

    # Relative footfall classification: the top ``high_share`` of poles by
    # footfall are HIGH, the next ``medium_share`` are MEDIUM, the rest LOW.
    footfall_high_share: float = 0.25
    footfall_medium_share: float = 0.40

    # Local time for shifts and "tomorrow" (IST, UTC+05:30; India has no DST).
    utc_offset_minutes: int = 330

    # --- Inventory & tariff (POC business rules, not an industry formula) ---
    # reserve = base_tariff_inr x pole_multiplier x shift_multiplier
    shifts: list[ShiftConfig] = DEFAULT_SHIFTS
    demand_multipliers: dict[str, float] = {
        "LOW": 0.6,
        "LOW_MEDIUM": 0.8,
        "MEDIUM": 1.0,
        "HIGH": 1.3,
        "VERY_HIGH": 1.6,
    }
    # Standard rate for one 2-hour shift (the formula's starting input).
    base_tariff_inr: int = 3_000
    tariff_footfall_weight: float = 0.7
    tariff_visibility_weight: float = 0.3
    # pole_value (0-100) maps linearly onto this multiplier range
    pole_multiplier_min: float = 0.5
    pole_multiplier_max: float = 2.0
    reserve_rounding_inr: int = 100
    # Slot multiplier from the slot's footfall vs. the pole's average slot:
    # (ratio ^ exponent) clamped to [min, max]. Exponent < 1 dampens extremes.
    slot_footfall_exponent: float = 0.6
    slot_multiplier_min: float = 0.5
    slot_multiplier_max: float = 1.8
    # Bidding is open for this many days ahead (each day's slots run their
    # qualifying round until 12:00 the day before).
    inventory_days_ahead: int = 7

    # --- Auctions: two rounds per slot ---
    # Qualifying round: anyone bids until ``qualifying_close_time`` on the day
    # before the ad date. Premium round: from ``premium_round_start_time`` that
    # day until ``premium_close_before_slot_minutes`` before the slot starts.
    qualifying_close_time: str = "12:00"
    premium_round_start_time: str = "16:00"
    premium_close_before_slot_minutes: int = 120
    # Each slot is a rolling ad shared equally by this many seats; the top
    # ``confirmed_seats`` qualifying bidders are confirmed at 12:00.
    seats_per_slot: int = 4
    confirmed_seats: int = 2
    # Premium bids start at this multiple of the top qualifying bid (rounded
    # up to ₹100). Anyone may bid; premium bids take seat 4, then seat 3.
    premium_floor_multiplier: float = 1.5
    # Every bid must beat the current highest bid by at least this much, so no
    # two bids can ever be equal.
    auction_min_increment_inr: int = 100

    # Expected-price ranges average past winning prices of the same pole,
    # shift and weekday over this many days.
    price_trend_days: int = 60
    # Background worker that starts due auctions and closes expired ones.
    auction_worker_enabled: bool = True
    auction_tick_seconds: float = 1.0


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

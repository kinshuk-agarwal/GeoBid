from app.core.config import settings
from app.footfall.provider import FootfallProvider, FootfallReading
from app.footfall.synthetic_provider import SyntheticFootfallProvider


def get_footfall_provider() -> FootfallProvider:
    """Return the configured provider. Register new providers here."""
    if settings.footfall_provider == "synthetic":
        return SyntheticFootfallProvider(settings.synthetic_data_dir)
    raise ValueError(f"Unknown footfall provider: {settings.footfall_provider!r}")


__all__ = ["FootfallProvider", "FootfallReading", "SyntheticFootfallProvider", "get_footfall_provider"]

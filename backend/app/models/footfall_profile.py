from sqlalchemy import ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class PoleFootfallProfile(Base):
    """Footfall for one pole in one hour of one weekday (from the footfall provider)."""

    __tablename__ = "pole_footfall_profiles"
    __table_args__ = (UniqueConstraint("pole_id", "weekday", "hour", name="uq_profile_pole_wd_hour"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    pole_id: Mapped[int] = mapped_column(ForeignKey("poles.id", ondelete="CASCADE"), index=True)
    weekday: Mapped[int] = mapped_column(Integer)  # Monday=0
    hour: Mapped[int] = mapped_column(Integer)  # 0-23
    footfall: Mapped[int] = mapped_column(Integer)

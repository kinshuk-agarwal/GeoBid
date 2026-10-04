from datetime import datetime

from sqlalchemy import JSON, Enum, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import FootfallCategory, PoleStatus
from app.models.types import UTCDateTime
from app.utils.time import utcnow


class Road(Base):
    """A major connectivity road. ``path`` is an approximate polyline of
    ``[lat, lng]`` points used for map rendering only."""

    __tablename__ = "roads"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160), unique=True)
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    importance_score: Mapped[int] = mapped_column(Integer, default=50)
    path: Mapped[list] = mapped_column(JSON, default=list)

    poles: Mapped[list["Pole"]] = relationship(back_populates="road")


class Pole(Base):
    """A digital advertising pole.

    ``footfall``, ``footfall_score`` and ``visibility_score`` are produced by
    an upstream footfall provider (synthetic in this POC); ``footfall_source``
    records which provider produced them. ``category`` is derived from the
    relative footfall distribution and recomputed whenever footfall changes.
    """

    __tablename__ = "poles"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(160))
    road_id: Mapped[int | None] = mapped_column(
        ForeignKey("roads.id", ondelete="SET NULL"), index=True
    )
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)

    footfall: Mapped[int] = mapped_column(Integer, default=0)
    footfall_score: Mapped[int] = mapped_column(Integer, default=0)
    visibility_score: Mapped[int] = mapped_column(Integer, default=0)
    footfall_source: Mapped[str] = mapped_column(String(40), default="synthetic")
    footfall_updated_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    category: Mapped[FootfallCategory] = mapped_column(
        Enum(FootfallCategory, native_enum=False, length=10),
        default=FootfallCategory.LOW,
        index=True,
    )

    status: Mapped[PoleStatus] = mapped_column(
        Enum(PoleStatus, native_enum=False, length=20), default=PoleStatus.ACTIVE
    )
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)

    road: Mapped[Road | None] = relationship(back_populates="poles")
    inventory_slots: Mapped[list["InventorySlot"]] = relationship(  # noqa: F821
        back_populates="pole", cascade="all, delete-orphan", passive_deletes=True
    )

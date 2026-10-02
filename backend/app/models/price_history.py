from datetime import date, datetime

from sqlalchemy import Date, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.types import UTCDateTime
from app.utils.time import utcnow


class SlotPriceHistory(Base):
    """Outcome of one pole-shift on one day: the winning price, or null if unsold.

    Written when an auction completes (``source="auction"``); for the POC the
    previous two months are back-filled synthetically (``source="synthetic"``).
    Used for price trends and the expected-price range.
    """

    __tablename__ = "slot_price_history"
    __table_args__ = (
        UniqueConstraint("pole_id", "date", "shift", name="uq_price_pole_date_shift"),
        Index("ix_price_pole_shift_date", "pole_id", "shift", "date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    pole_id: Mapped[int] = mapped_column(ForeignKey("poles.id", ondelete="CASCADE"))
    date: Mapped[date] = mapped_column(Date)
    shift: Mapped[str] = mapped_column(String(8))
    base_price: Mapped[int] = mapped_column(Integer)
    clearing_price: Mapped[int | None] = mapped_column(Integer)  # null = unsold
    bid_count: Mapped[int] = mapped_column(Integer, default=0)
    source: Mapped[str] = mapped_column(String(20), default="auction")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)

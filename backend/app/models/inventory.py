from datetime import date, datetime

from sqlalchemy import Date, Enum, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import SlotStatus
from app.models.types import UTCDateTime
from app.utils.time import utcnow


class InventorySlot(Base):
    """One auctionable unit: a pole, on a date, during one shift."""

    __tablename__ = "inventory_slots"
    __table_args__ = (UniqueConstraint("pole_id", "date", "shift", name="uq_slot_pole_date_shift"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    pole_id: Mapped[int] = mapped_column(ForeignKey("poles.id", ondelete="CASCADE"), index=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    shift: Mapped[str] = mapped_column(String(8))  # shift code, e.g. "S5"
    base_tariff: Mapped[int] = mapped_column(Integer)  # INR
    reserve_price: Mapped[int] = mapped_column(Integer)  # INR
    status: Mapped[SlotStatus] = mapped_column(
        Enum(SlotStatus, native_enum=False, length=20), default=SlotStatus.AVAILABLE, index=True
    )
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)

    pole: Mapped["Pole"] = relationship(back_populates="inventory_slots")  # noqa: F821
    auction: Mapped["Auction | None"] = relationship(  # noqa: F821
        back_populates="inventory_slot",
        cascade="all, delete-orphan",
        passive_deletes=True,
        uselist=False,
    )

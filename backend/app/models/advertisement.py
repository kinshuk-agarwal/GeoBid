from datetime import datetime

from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.types import UTCDateTime
from app.utils.time import utcnow


class Advertisement(Base):
    """Creative an advertiser intends to display."""

    __tablename__ = "advertisements"

    id: Mapped[int] = mapped_column(primary_key=True)
    advertiser_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(160))
    description: Mapped[str | None] = mapped_column(Text)
    image_url: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class WinningAdvertisement(Base):
    """A booked seat in a slot's rolling ad: one row per winning advertiser.

    Each seat holder pays their own bid; the ad rotates equally among seats.
    """

    __tablename__ = "winning_advertisements"
    __table_args__ = (UniqueConstraint("auction_id", "advertiser_id", name="uq_winner_per_auction"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    auction_id: Mapped[int] = mapped_column(ForeignKey("auctions.id", ondelete="CASCADE"), index=True)
    seat: Mapped[int] = mapped_column(Integer, default=1)
    advertiser_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    advertisement_id: Mapped[int | None] = mapped_column(
        ForeignKey("advertisements.id", ondelete="SET NULL")
    )
    winning_bid: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)

    auction: Mapped["Auction"] = relationship(back_populates="winners")  # noqa: F821
    advertiser: Mapped["User"] = relationship()  # noqa: F821
    advertisement: Mapped[Advertisement | None] = relationship()

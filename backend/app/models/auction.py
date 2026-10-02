from datetime import datetime

from sqlalchemy import Enum, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import AuctionRound, AuctionStatus
from app.models.types import UTCDateTime
from app.utils.time import utcnow


class Auction(Base):
    """A two-round auction for the 4 rotating ad seats of one inventory slot.

    Qualifying round [start_time, qualifying_end_time): anyone bids; the top 4
                     hold seats.
    Break            [qualifying_end_time, premium_start_time): seats 1-2 are
                     confirmed; no bidding.
    Premium round    [premium_start_time, end_time): anyone bids from the
                     premium floor to take seat 4, then seat 3.

    ``reserve_price`` is the base price (copied from the slot, admin may
    override); ``min_increment`` is the minimum gap between bids. ``version``
    is bumped on every accepted bid so concurrent bids can't both apply.
    """

    __tablename__ = "auctions"

    id: Mapped[int] = mapped_column(primary_key=True)
    inventory_slot_id: Mapped[int] = mapped_column(
        ForeignKey("inventory_slots.id", ondelete="CASCADE"), unique=True
    )
    start_time: Mapped[datetime] = mapped_column(UTCDateTime)
    qualifying_end_time: Mapped[datetime] = mapped_column(UTCDateTime, index=True)
    premium_start_time: Mapped[datetime] = mapped_column(UTCDateTime, index=True)
    end_time: Mapped[datetime] = mapped_column(UTCDateTime, index=True)
    reserve_price: Mapped[int] = mapped_column(Integer)
    min_increment: Mapped[int] = mapped_column(Integer, default=100)
    # Premium-round starting price (1.5x the top qualifying bid), set at 12:00.
    premium_floor: Mapped[int | None] = mapped_column(Integer)
    # Highest bid so far (any seat), kept for listings.
    current_highest_bid: Mapped[int | None] = mapped_column(Integer)
    current_highest_bidder_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    version: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[AuctionStatus] = mapped_column(
        Enum(AuctionStatus, native_enum=False, length=20),
        default=AuctionStatus.SCHEDULED,
        index=True,
    )
    round: Mapped[AuctionRound] = mapped_column(
        Enum(AuctionRound, native_enum=False, length=20), default=AuctionRound.QUALIFYING, index=True
    )
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime)

    inventory_slot: Mapped["InventorySlot"] = relationship(back_populates="auction")  # noqa: F821
    current_highest_bidder: Mapped["User | None"] = relationship()  # noqa: F821
    bids: Mapped[list["Bid"]] = relationship(
        back_populates="auction",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="Bid.timestamp",
    )
    confirmed_seats: Mapped[list["ConfirmedSeat"]] = relationship(
        back_populates="auction",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="ConfirmedSeat.seat",
    )
    winners: Mapped[list["WinningAdvertisement"]] = relationship(  # noqa: F821
        back_populates="auction",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="WinningAdvertisement.seat",
    )


class Bid(Base):
    __tablename__ = "bids"
    __table_args__ = (Index("ix_bids_auction_amount", "auction_id", "amount"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    auction_id: Mapped[int] = mapped_column(ForeignKey("auctions.id", ondelete="CASCADE"))
    advertiser_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    amount: Mapped[int] = mapped_column(Integer)  # INR
    round: Mapped[str] = mapped_column(String(20), default="QUALIFYING")  # QUALIFYING | PREMIUM
    timestamp: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)

    auction: Mapped[Auction] = relationship(back_populates="bids")
    advertiser: Mapped["User"] = relationship()  # noqa: F821


class ConfirmedSeat(Base):
    """A seat secured at 12:00 by one of the top qualifying bidders."""

    __tablename__ = "auction_confirmed_seats"
    __table_args__ = (UniqueConstraint("auction_id", "advertiser_id", name="uq_confirmed_seat"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    auction_id: Mapped[int] = mapped_column(ForeignKey("auctions.id", ondelete="CASCADE"), index=True)
    advertiser_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    seat: Mapped[int] = mapped_column(Integer)  # 1 = highest qualifying bid
    amount: Mapped[int] = mapped_column(Integer)

    auction: Mapped[Auction] = relationship(back_populates="confirmed_seats")

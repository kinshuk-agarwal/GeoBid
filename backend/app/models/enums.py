"""Enumerations shared by models, schemas and services."""

import enum


class UserRole(str, enum.Enum):
    OWNER = "OWNER"
    ADVERTISER = "ADVERTISER"
    ADMIN = "ADMIN"


class FootfallCategory(str, enum.Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class PoleStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


class SlotStatus(str, enum.Enum):
    AVAILABLE = "AVAILABLE"  # no auction yet
    IN_AUCTION = "IN_AUCTION"  # auction scheduled or live
    SOLD = "SOLD"  # auction completed with a winner
    UNSOLD = "UNSOLD"  # auction completed without valid bids


class AuctionStatus(str, enum.Enum):
    SCHEDULED = "SCHEDULED"
    LIVE = "LIVE"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class AuctionRound(str, enum.Enum):
    """Where a LIVE auction is in its two-round schedule."""

    QUALIFYING = "QUALIFYING"  # anyone may bid until 12:00; top 4 hold seats
    BREAK = "BREAK"  # 12:00-16:00: seats 1-2 confirmed; no bidding
    PREMIUM = "PREMIUM"  # anyone (but confirmed holders) bids for seats 3-4
    CLOSED = "CLOSED"

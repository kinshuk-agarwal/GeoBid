"""ORM models. Importing this package registers every table on ``Base``."""

from app.models.advertisement import Advertisement, WinningAdvertisement
from app.models.auction import Auction, Bid, ConfirmedSeat
from app.models.footfall_profile import PoleFootfallProfile
from app.models.enums import AuctionRound, AuctionStatus, FootfallCategory, PoleStatus, SlotStatus, UserRole
from app.models.inventory import InventorySlot
from app.models.pole import Pole, Road
from app.models.price_history import SlotPriceHistory
from app.models.user import User

__all__ = [
    "Advertisement",
    "Auction",
    "AuctionRound",
    "AuctionStatus",
    "Bid",
    "ConfirmedSeat",
    "FootfallCategory",
    "InventorySlot",
    "Pole",
    "PoleFootfallProfile",
    "PoleStatus",
    "Road",
    "SlotPriceHistory",
    "SlotStatus",
    "User",
    "UserRole",
    "WinningAdvertisement",
]

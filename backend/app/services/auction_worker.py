"""Lightweight background loop that drives auction timing."""

import asyncio
import logging

from app.core.config import settings
from app.core.database import SessionLocal
from app.services import auction_service
from app.services.events import AuctionEvent, event_bus

log = logging.getLogger(__name__)


def _tick() -> list[AuctionEvent]:
    with SessionLocal() as db:
        return auction_service.process_due(db)


async def run_auction_worker(stop: asyncio.Event) -> None:
    log.info("Auction worker started (tick %.1fs)", settings.auction_tick_seconds)
    while not stop.is_set():
        try:
            # DB work happens in a thread so the event loop stays responsive.
            events = await asyncio.to_thread(_tick)
            if events:
                event_bus.publish(events)
        except Exception:  # pragma: no cover - keep the loop alive
            log.exception("Auction worker tick failed")
        try:
            await asyncio.wait_for(stop.wait(), timeout=settings.auction_tick_seconds)
        except asyncio.TimeoutError:
            pass

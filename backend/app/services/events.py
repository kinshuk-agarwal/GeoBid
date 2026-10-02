"""In-process auction event bus.

Auction services return ``AuctionEvent`` objects; callers publish them here.
Delivery (e.g. WebSocket broadcast) subscribes to the bus, so bid validation
never depends on transport code.

``publish`` is thread-safe (sync route handlers run in a thread pool). Events
go through one queue drained by a single task, so subscribers receive them in
publish order, e.g. NEW_BID for ₹17,000 always before NEW_BID for ₹17,500.
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from app.utils.time import utcnow

log = logging.getLogger(__name__)


class EventType(str, Enum):
    NEW_BID = "NEW_BID"
    OUTBID = "OUTBID"
    AUCTION_STARTED = "AUCTION_STARTED"
    QUALIFYING_CLOSED = "QUALIFYING_CLOSED"  # 12:00: seats 1-2 confirmed, premium floor set
    PREMIUM_ROUND_STARTED = "PREMIUM_ROUND_STARTED"
    AUCTION_COMPLETED = "AUCTION_COMPLETED"


@dataclass(frozen=True)
class AuctionEvent:
    type: EventType
    auction_id: int
    data: dict = field(default_factory=dict)
    timestamp: datetime = field(default_factory=utcnow)

    def to_message(self) -> dict:
        return {
            "type": self.type.value,
            "auction_id": self.auction_id,
            "timestamp": self.timestamp.isoformat(),
            **self.data,
        }


Subscriber = Callable[[AuctionEvent], Awaitable[None]]


class EventBus:
    def __init__(self) -> None:
        self._subscribers: list[Subscriber] = []
        self._loop: asyncio.AbstractEventLoop | None = None
        self._queue: asyncio.Queue[AuctionEvent | None] | None = None
        self._task: asyncio.Task | None = None

    def subscribe(self, fn: Subscriber) -> Callable[[], None]:
        self._subscribers.append(fn)
        return lambda: self._subscribers.remove(fn)

    async def start(self) -> None:
        """Begin dispatching on the running loop (called at app startup)."""
        self._loop = asyncio.get_running_loop()
        self._queue = asyncio.Queue()
        self._task = asyncio.create_task(self._dispatch())

    async def stop(self) -> None:
        if self._queue is not None and self._task is not None:
            self._queue.put_nowait(None)
            await self._task
        self._loop = self._queue = self._task = None

    def publish(self, events: AuctionEvent | Iterable[AuctionEvent]) -> None:
        loop, queue = self._loop, self._queue
        if loop is None or queue is None or loop.is_closed():
            return  # no running app (scripts, unit tests)
        for event in [events] if isinstance(events, AuctionEvent) else events:
            loop.call_soon_threadsafe(queue.put_nowait, event)

    async def _dispatch(self) -> None:
        assert self._queue is not None
        while (event := await self._queue.get()) is not None:
            for sub in list(self._subscribers):
                try:
                    await sub(event)
                except Exception:  # pragma: no cover - defensive
                    log.exception("Auction event subscriber failed for %s", event)


event_bus = EventBus()

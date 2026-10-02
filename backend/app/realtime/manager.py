"""WebSocket connection manager: one room per auction."""

import asyncio
import logging
from collections import defaultdict

from fastapi import WebSocket

from app.services.events import AuctionEvent

log = logging.getLogger(__name__)

SEND_TIMEOUT_S = 5.0


class AuctionConnectionManager:
    def __init__(self) -> None:
        self._rooms: dict[int, set[WebSocket]] = defaultdict(set)

    def viewers(self, auction_id: int) -> int:
        return len(self._rooms.get(auction_id, ()))

    def add(self, auction_id: int, ws: WebSocket) -> None:
        self._rooms[auction_id].add(ws)

    async def announce_viewers(self, auction_id: int) -> None:
        await self.broadcast(auction_id, {"type": "VIEWERS", "auction_id": auction_id, "count": self.viewers(auction_id)})

    async def leave(self, auction_id: int, ws: WebSocket) -> None:
        room = self._rooms.get(auction_id)
        if room is None:
            return
        room.discard(ws)
        if room:
            await self.announce_viewers(auction_id)
        else:
            self._rooms.pop(auction_id, None)

    async def broadcast(self, auction_id: int, message: dict) -> None:
        sockets = list(self._rooms.get(auction_id, ()))
        if not sockets:
            return
        results = await asyncio.gather(*(self._send(ws, message) for ws in sockets), return_exceptions=True)
        # Drop sockets that failed (closed tabs, stalled clients).
        for ws, result in zip(sockets, results):
            if isinstance(result, Exception):
                self._rooms.get(auction_id, set()).discard(ws)

    @staticmethod
    async def _send(ws: WebSocket, message: dict) -> None:
        await asyncio.wait_for(ws.send_json(message), SEND_TIMEOUT_S)

    async def on_event(self, event: AuctionEvent) -> None:
        """Event-bus subscriber: forward auction events to that auction's room."""
        await self.broadcast(event.auction_id, event.to_message())


manager = AuctionConnectionManager()

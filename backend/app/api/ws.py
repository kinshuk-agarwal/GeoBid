"""WebSocket endpoint for live auction updates.

    ws://<host>/ws/auctions/{auction_id}

Server -> client messages (JSON, field ``type``):
    SNAPSHOT           full auction state + bid history, sent on connect
    NEW_BID            a bid was accepted
    OUTBID             the previous leader (``outbid_user_id``) was outbid
    AUCTION_STARTED    a scheduled auction went live
    AUCTION_COMPLETED  bidding closed; ``winner_id`` / ``winning_bid``
    VIEWERS            number of connected viewers
    PONG               reply to a client ``{"type": "PING"}``

The socket is read-only: bids are placed via ``POST /api/auctions/{id}/bids``
so validation and authentication stay in one place.
"""

import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status
from fastapi.encoders import jsonable_encoder

from app.core.database import SessionLocal
from app.core.exceptions import NotFoundError
from app.realtime.manager import manager
from app.services import auction_service
from app.services.auction_views import auction_out, to_bid_out

router = APIRouter()


def _exists(auction_id: int) -> bool:
    with SessionLocal() as db:
        try:
            auction_service.get_auction(db, auction_id)
            return True
        except NotFoundError:
            return False


def _snapshot(auction_id: int) -> dict:
    with SessionLocal() as db:
        auction = auction_service.get_auction(db, auction_id)
        return jsonable_encoder(
            {
                "type": "SNAPSHOT",
                "auction_id": auction_id,
                "auction": auction_out(db, auction),
                "bids": [to_bid_out(b) for b in auction_service.list_bids(db, auction_id)],
            }
        )


@router.websocket("/ws/auctions/{auction_id}")
async def auction_socket(websocket: WebSocket, auction_id: int) -> None:
    if not await asyncio.to_thread(_exists, auction_id):
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Auction not found")
        return

    await websocket.accept()
    # Join the room before taking the snapshot so no event can fall between
    # them. A bid may then arrive both live and in the snapshot; clients
    # de-duplicate by bid id.
    manager.add(auction_id, websocket)
    try:
        await websocket.send_json(await asyncio.to_thread(_snapshot, auction_id))
        await manager.announce_viewers(auction_id)
        while True:
            msg = await websocket.receive_json()
            if isinstance(msg, dict) and msg.get("type") == "PING":
                await websocket.send_json({"type": "PONG"})
    except (WebSocketDisconnect, ValueError):
        pass
    finally:
        await manager.leave(auction_id, websocket)

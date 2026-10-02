"""WebSocket flow: bid submitted -> backend updates auction -> event
generated -> every connected client receives it."""

import asyncio
from datetime import timedelta

import pytest
from starlette.websockets import WebSocketDisconnect

from app.core.config import settings
from app.models import InventorySlot, Pole, UserRole
from app.services import auction_service
from app.services import shifts as shift_svc
from app.services.events import AuctionEvent, EventBus, EventType
from app.utils.time import utcnow
from scripts.seed_database import seed_all


@pytest.fixture
def auction(db, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "synthetic_data_dir", tmp_path)
    seed_all(db, tmp_path, demo_auctions=False, price_history=False)
    pole = db.query(Pole).filter_by(code="P014").one()
    slot = db.query(InventorySlot).filter_by(pole_id=pole.id, date=shift_svc.tomorrow(), shift="S9").one()
    now = utcnow()
    a, _ = auction_service.create_auction(
        db,
        slot_id=slot.id,
        qualifying_end_time=now + timedelta(minutes=30),
        premium_start_time=now + timedelta(minutes=60),
        end_time=now + timedelta(minutes=120),
        now=now,
    )
    return a


def recv_until(ws, type_: str, limit: int = 20) -> dict:
    """Read messages until one of ``type_`` arrives (skips VIEWERS etc.)."""
    for _ in range(limit):
        msg = ws.receive_json()
        if msg["type"] == type_:
            return msg
    raise AssertionError(f"no {type_} message received")


def test_snapshot_on_connect(client, auction):
    with client.websocket_connect(f"/ws/auctions/{auction.id}") as ws:
        snap = ws.receive_json()
        assert snap["type"] == "SNAPSHOT"
        assert snap["auction"]["id"] == auction.id
        assert snap["auction"]["status"] == "LIVE"
        assert snap["bids"] == []
        assert recv_until(ws, "VIEWERS")["count"] == 1


def test_unknown_auction_rejected(client, auction):
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/ws/auctions/999999") as ws:
            ws.receive_json()


def test_ping_pong(client, auction):
    with client.websocket_connect(f"/ws/auctions/{auction.id}") as ws:
        ws.receive_json()
        ws.send_json({"type": "PING"})
        recv_until(ws, "PONG")


def test_bids_broadcast_to_all_clients(client, auction, auth_headers):
    """Five advertisers compete for 4 seats: everyone connected sees every
    accepted bid; the bidder pushed out of the seats gets OUTBID."""
    h = [auth_headers(f"a{i}@example.com") for i in range(5)]
    admin = auth_headers("root@example.com", UserRole.ADMIN)
    r = auction.reserve_price

    with (
        client.websocket_connect(f"/ws/auctions/{auction.id}") as ws1,
        client.websocket_connect(f"/ws/auctions/{auction.id}") as ws2,
    ):
        # A VIEWERS update may precede the snapshot (clients join the room
        # before the snapshot is taken), so wait for it rather than assume.
        recv_until(ws1, "SNAPSHOT")
        recv_until(ws2, "SNAPSHOT")

        # Bid via REST -> both sockets get NEW_BID with the seat board
        res = client.post(f"/api/auctions/{auction.id}/bids", json={"amount": r}, headers=h[0])
        assert res.status_code == 201, res.text
        lowest = res.json()["bid"]["advertiser_id"]
        for ws in (ws1, ws2):
            msg = recv_until(ws, "NEW_BID")
            assert msg["auction_id"] == auction.id and msg["amount"] == r and msg["bid_count"] == 1
            assert [s["status"] for s in msg["seats"]] == ["LEADING", "OPEN", "OPEN", "OPEN"]
            assert msg["timestamp"]

        # Three more fill the seats (no one is pushed out yet)
        for i in (1, 2, 3):
            client.post(f"/api/auctions/{auction.id}/bids", json={"amount": r + 100 * i}, headers=h[i])
            for ws in (ws1, ws2):
                assert recv_until(ws, "NEW_BID")["amount"] == r + 100 * i

        # A fifth bidder takes a seat -> NEW_BID, then OUTBID for the lowest seat
        client.post(f"/api/auctions/{auction.id}/bids", json={"amount": r + 400}, headers=h[4])
        for ws in (ws1, ws2):
            new = recv_until(ws, "NEW_BID")
            assert new["amount"] == r + 400 and lowest not in [s["advertiser_id"] for s in new["seats"]]
            out = ws.receive_json()
            assert out["type"] == "OUTBID" and out["outbid_user_id"] == lowest

        # Rejected bids broadcast nothing; completion broadcasts all winners
        assert client.post(f"/api/auctions/{auction.id}/bids", json={"amount": r}, headers=h[0]).status_code == 422
        client.post(f"/api/auctions/{auction.id}/complete", headers=admin)
        for ws in (ws1, ws2):
            done = recv_until(ws, "AUCTION_COMPLETED")
            assert [w["amount"] for w in done["winners"]] == [r + 400, r + 300, r + 200, r + 100]
            assert done["revenue"] == 4 * r + 1000 and done["slot_status"] == "SOLD"


def test_round_changes_broadcast(client, auction, auth_headers):
    admin = auth_headers("root@example.com", UserRole.ADMIN)
    h1, h2 = auth_headers("a1@example.com"), auth_headers("a2@example.com")
    r = auction.reserve_price
    client.post(f"/api/auctions/{auction.id}/bids", json={"amount": r}, headers=h1)
    client.post(f"/api/auctions/{auction.id}/bids", json={"amount": r + 100}, headers=h2)
    with client.websocket_connect(f"/ws/auctions/{auction.id}") as ws:
        recv_until(ws, "SNAPSHOT")
        client.post(f"/api/auctions/{auction.id}/advance", headers=admin)
        closed = recv_until(ws, "QUALIFYING_CLOSED")
        assert len(closed["confirmed_ids"]) == 2
        assert [s["status"] for s in closed["seats"]] == ["CONFIRMED", "CONFIRMED", "OPEN", "OPEN"]
        assert closed["premium_floor"] == -(-(r + 100) * 3 // 200) * 100  # 1.5x top, rounded up to 100
        client.post(f"/api/auctions/{auction.id}/advance", headers=admin)
        started = recv_until(ws, "PREMIUM_ROUND_STARTED")
        assert started["premium_floor"] == closed["premium_floor"]


def test_event_bus_preserves_order():
    async def run():
        bus = EventBus()
        seen: list[int] = []

        async def slow_subscriber(e: AuctionEvent):
            await asyncio.sleep(0.01 if e.data["n"] % 2 == 0 else 0)
            seen.append(e.data["n"])

        bus.subscribe(slow_subscriber)
        await bus.start()
        bus.publish([AuctionEvent(EventType.NEW_BID, 1, {"n": i}) for i in range(10)])
        await asyncio.sleep(0.3)
        await bus.stop()
        return seen

    assert asyncio.run(run()) == list(range(10))

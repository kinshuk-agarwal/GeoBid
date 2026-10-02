import os
import tempfile
from pathlib import Path

# Must be set before any app module is imported. A temporary *file* database
# (like production) rather than in-memory: an in-memory database shares one
# connection across threads, which races when a WebSocket snapshot and a bid
# hit it at the same time.
_TEST_DB = Path(tempfile.mkdtemp(prefix="geobid-tests-")) / "test.db"
os.environ["GEOBID_DATABASE_URL"] = f"sqlite:///{_TEST_DB.as_posix()}"
os.environ["GEOBID_BCRYPT_ROUNDS"] = "4"  # fast hashing in tests
# Tests drive auction timing explicitly instead of via the background worker.
os.environ["GEOBID_AUCTION_WORKER_ENABLED"] = "false"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.core.database import SessionLocal, reset_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models import UserRole  # noqa: E402
from app.services.auth_service import create_user  # noqa: E402


@pytest.fixture(autouse=True)
def _fresh_db():
    reset_db()
    yield


@pytest.fixture
def db():
    with SessionLocal() as session:
        yield session


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def make_user(db):
    def _make(email: str, role: UserRole = UserRole.ADVERTISER, password: str = "password123"):
        return create_user(db, name=email.split("@")[0], email=email, password=password, role=role)

    return _make


@pytest.fixture
def auth_headers(client, make_user):
    """Return a function producing Authorization headers for a new user."""

    def _headers(email: str, role: UserRole = UserRole.ADVERTISER) -> dict:
        make_user(email, role)
        res = client.post("/api/auth/login", json={"email": email, "password": "password123"})
        assert res.status_code == 200, res.text
        return {"Authorization": f"Bearer {res.json()['access_token']}"}

    return _headers

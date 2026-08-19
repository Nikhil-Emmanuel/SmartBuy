"""Shared fixtures for the API integration suite.

These tests run against the seeded SQLite catalog through TestClient rather
than against a mock. The point of the suite is to catch contract drift between
the backend and the frontend, and a mocked backend cannot drift.

Requires `python backend/scripts/seed.py` to have been run. Tests skip rather
than fail when the catalog is empty, so a fresh clone reports "not seeded"
instead of 40 confusing assertion errors.
"""

from __future__ import annotations

import uuid

import pytest
from app.core.config import settings
from app.main import app
from fastapi.testclient import TestClient


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="session", autouse=True)
def require_seeded_catalog(client):
    health = client.get("/api/health").json()
    if not health.get("catalog_size"):
        pytest.skip("catalog is empty -- run `python backend/scripts/seed.py`")


@pytest.fixture
def session_id() -> str:
    """A fresh anonymous user per test.

    Sessions accumulate conversation state, so sharing one across tests would
    make them order-dependent -- the exact failure mode that makes a suite
    untrustworthy the week before a demo.
    """
    return str(uuid.uuid4())


@pytest.fixture
def headers(session_id) -> dict[str, str]:
    return {"X-Session-Id": session_id}


@pytest.fixture
def admin_headers() -> dict[str, str]:
    return {"X-Admin-Token": settings.ADMIN_TOKEN}


def ok(response, expected: int = 200):
    """Assert the status code, showing the body when it does not match."""
    assert response.status_code == expected, (
        f"{response.request.method} {response.request.url.path} -> "
        f"{response.status_code} (expected {expected}): {response.text[:500]}"
    )
    return response.json()


@pytest.fixture
def winter_trek_plan(client, headers):
    """The primary demo journey, run once and reused by several tests.

    Returns (plan_id, first_turn, second_turn).
    """
    turn1 = ok(
        client.post(
            "/api/chat",
            headers=headers,
            json={
                "message": "I'm going for a 4-day winter trek in Manali, budget Rs 15,000, "
                "I'm a beginner, I already have trekking shoes and a backpack"
            },
        )
    )
    turn2 = ok(
        client.post(
            "/api/chat",
            headers=headers,
            json={"session_id": turn1["session_id"], "message": "Camping overnight"},
        )
    )
    plan_id = turn2["plan_id"] or turn1["plan_id"]
    assert plan_id, f"no plan produced by the demo journey: {turn2}"
    return plan_id, turn1, turn2

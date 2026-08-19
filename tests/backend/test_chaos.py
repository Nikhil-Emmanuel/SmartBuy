"""Chaos: the system must stay usable when its dependencies do not.

The demo has one hard external dependency (Gemini) and one soft one (the
catalog). A hackathon demo that dies when the venue wifi drops, or when the
free-tier quota runs out mid-presentation, is a demo that does not happen.

The Gemini free tier allows 15 requests/minute. During development this suite
exhausted it on its own and the deterministic fallback absorbed it without a
single 5xx -- which is the behaviour these tests pin down.
"""

from __future__ import annotations

import pytest
from app.agent import llm as llm_module

from .conftest import ok

pytestmark = pytest.mark.integration


class ExplodingProvider(llm_module.LLMProvider):
    """Configured, reachable, and fails on every call.

    Deliberately reports `available = True`: unsetting GEMINI_API_KEY would
    exercise the never-configured branch (NullProvider), which the orchestrator
    handles differently from a provider that was working and then broke. The
    mid-demo outage is the one worth testing.
    """

    name = "exploding"

    def __init__(self) -> None:
        self.calls = 0

    def generate_json(self, system: str, user: str, max_output_tokens: int = 1024) -> dict:
        self.calls += 1
        raise llm_module.LLMUnavailable("simulated Gemini outage")

    @property
    def available(self) -> bool:
        return True


@pytest.fixture
def llm_always_fails(monkeypatch):
    provider = ExplodingProvider()
    monkeypatch.setattr(llm_module, "get_llm_provider", lambda: provider)
    # The orchestrator imports the getter by name, so the module that actually
    # calls it has to be patched too.
    import app.agent.orchestrator as orchestrator

    if hasattr(orchestrator, "get_llm_provider"):
        monkeypatch.setattr(orchestrator, "get_llm_provider", lambda: provider)
    return provider


class TestLlmOutage:
    def test_chat_still_answers_when_gemini_is_down(self, client, headers, llm_always_fails):
        response = client.post(
            "/api/chat",
            headers=headers,
            json={"message": "I'm going for a 4-day winter trek in Manali, budget Rs 15,000"},
        )
        body = ok(response)
        assert llm_always_fails.calls > 0, (
            "the exploding provider was never called, so this test proves "
            "nothing about the outage path"
        )
        assert body["assistant_message"].strip(), "outage produced an empty reply"
        assert body["degraded"] is True, (
            "the LLM failed but the response was not marked degraded -- the UI "
            "banner is how we stay honest about that"
        )

    def test_outage_still_extracts_slots_deterministically(
        self, client, headers, llm_always_fails
    ):
        """The regex NLU is the floor. Budget is the slot the demo cannot lose."""
        body = ok(
            client.post(
                "/api/chat",
                headers=headers,
                json={"message": "4-day winter trek in Manali, budget Rs 15,000, beginner"},
            )
        )
        assert body["slots"]["budget_total"] == 15000, body["slots"]

    def test_outage_never_returns_5xx(self, client, headers, llm_always_fails):
        for message in ("hello", "camping trip for 3 people", "budget 20000"):
            response = client.post("/api/chat", headers=headers, json={"message": message})
            assert response.status_code < 500, (
                f"{message!r} -> {response.status_code}: {response.text[:300]}"
            )


class TestMalformedInput:
    @pytest.mark.parametrize(
        "payload",
        [
            {},
            {"message": ""},
            {"message": None},
            {"message": 12345},
            {"message": "hi", "session_id": 99},
        ],
    )
    def test_bad_chat_payloads_are_rejected_not_crashed(self, client, headers, payload):
        response = client.post("/api/chat", headers=headers, json=payload)
        assert response.status_code in (200, 422), response.text[:300]
        if response.status_code == 422:
            assert response.json()["error"]["code"] == "VALIDATION_ERROR"

    def test_oversized_message_is_rejected(self, client, headers):
        response = client.post("/api/chat", headers=headers, json={"message": "x" * 50_000})
        assert response.status_code in (200, 413, 422), response.status_code

    @pytest.mark.parametrize(
        "params",
        [
            {"page": -1},
            {"page": 0},
            {"page_size": 0},
            {"page_size": 100_000},
            {"min_price": "abc"},
            {"max_price": -5},
            {"sort": "'; DROP TABLE products; --"},
        ],
    )
    def test_bad_search_params_do_not_crash(self, client, params):
        response = client.get("/api/products/search", params=params)
        assert response.status_code in (200, 422), (
            f"{params} -> {response.status_code}: {response.text[:300]}"
        )

    def test_sql_injection_in_query_is_parameterized_away(self, client):
        """SQLAlchemy binds parameters, but a demo that claims it should prove it."""
        before = ok(client.get("/api/products/search", params={"page_size": 1}))["total"]
        ok(client.get("/api/products/search", params={"q": "'; DROP TABLE products; --"}))
        after = ok(client.get("/api/products/search", params={"page_size": 1}))["total"]
        assert after == before, "the catalog changed size after an injection attempt"


class TestUnknownIdentifiers:
    @pytest.mark.parametrize(
        ("method", "path", "payload"),
        [
            ("get", "/api/products/nope", None),
            ("get", "/api/requirements/nope", None),
            ("get", "/api/shopping-plan/nope", None),
            ("get", "/api/session/nope", None),
            ("post", "/api/bundle/optimize", {"plan_id": "nope"}),
            ("post", "/api/recommendations", {"plan_id": "nope"}),
        ],
    )
    def test_unknown_ids_are_404_not_500(self, client, headers, method, path, payload):
        call = getattr(client, method)
        response = call(path, headers=headers, json=payload) if payload else call(path)
        assert response.status_code == 404, (
            f"{method.upper()} {path} -> {response.status_code}: {response.text[:300]}"
        )
        assert response.json()["error"]["code"].endswith("NOT_FOUND")


class TestUnknownMarketplaceKeys:
    def test_stale_toggle_key_is_ignored_not_fatal(self, client):
        """A marketplace key left in someone's localStorage after we rename or
        retire a source must not 400 their whole session."""
        response = client.get(
            "/api/products/search", params={"sources": "MARKET_A,RETIRED_SOURCE"}
        )
        data = ok(response)
        assert {item["source"] for item in data["items"]} <= {"MARKET_A"}

    def test_only_unknown_keys_yields_no_products(self, client):
        """An explicit selection that validates down to nothing stays empty
        rather than falling back to every marketplace."""
        data = ok(client.get("/api/products/search", params={"sources": "RETIRED_SOURCE"}))
        assert data["total"] == 0, data["total"]

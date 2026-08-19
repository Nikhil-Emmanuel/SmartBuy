"""Natural-language handling: the chat must answer what was typed.

Every test here is a regression. A user typed "mobile" into a conversation
about trekking shoes and was shown the shoes again, under the shoes' budget,
three separate defects deep:

  1. any message of two words or fewer was classified as small talk, so
     "mobile" got a greeting instead of a search;
  2. "trekking shoes" extracted activity="trek", and the router sent anything
     with an activity down the goal branch -- answering a request for one pair
     of shoes with a fifteen-item trek kit;
  3. `Slots.merge` keeps the first goal_text it ever sees, so a new subject
     never displaced the old one and the old plan was simply re-rendered.

These assert on routing and slots rather than on prose, because the prose comes
from Gemini and changes between runs.
"""

from __future__ import annotations

import pytest

from .conftest import ok

pytestmark = pytest.mark.integration


def say(client, headers, message: str, session_id: str | None = None) -> dict:
    payload = {"message": message}
    if session_id:
        payload["session_id"] = session_id
    return ok(client.post("/api/chat", headers=headers, json=payload))


class TestShortMessagesAreNotSmallTalk:
    @pytest.mark.parametrize("message", ["mobile", "laptop", "headphones", "tent"])
    def test_a_bare_product_noun_starts_a_search(self, client, headers, message):
        """Naming a product is the most natural way there is to open a search.

        Answering it with "tell me what you are shopping for" is the robotic
        behaviour the small-talk check was supposed to prevent, not cause.
        """
        body = say(client, headers, message)
        assert message in body["assistant_message"].lower(), (
            f"{message!r} was answered without ever mentioning it: "
            f"{body['assistant_message'][:200]}"
        )

    @pytest.mark.parametrize("message", ["hi", "hello", "thanks", "ok"])
    def test_greetings_still_get_a_greeting(self, client, headers, message):
        body = say(client, headers, message)
        assert body["plan_id"] is None, f"{message!r} built a plan"
        assert body["chips"], "the greeting dropped its starter chips"


class TestProductSearchIsNotHijackedByAnActivityWord:
    def test_trekking_shoes_searches_for_shoes_not_a_trek(self, client, headers):
        """"Trekking shoes" extracts activity="trek". It is still one product."""
        body = say(client, headers, "I need trekking shoes under 20000")
        assert body["plan_id"], body
        reqs = ok(client.get(f"/api/requirements/{body['plan_id']}"))
        buckets = reqs["requirements"]
        total = sum(len(items) for items in buckets.values())
        assert total == 1, (
            f"a request for one pair of shoes produced {total} requirements -- "
            "this is the goal planner answering a product search"
        )

    def test_a_purpose_clause_still_reaches_the_goal_planner(self, client, headers):
        """The distinction is the purpose clause, not the noun: "for my trek"
        is a situation, "trekking shoes" is a product."""
        body = say(client, headers, "I need a tent for my trek")
        for _ in range(6):
            if body["plan_id"]:
                break
            body = say(client, headers, "That's everything, go ahead", body["session_id"])
        assert body["plan_id"], body
        reqs = ok(client.get(f"/api/requirements/{body['plan_id']}"))
        total = sum(len(items) for items in reqs["requirements"].values())
        assert total > 1, "a goal-shaped message produced a single-product search"


class TestChangingTheSubject:
    def test_a_new_subject_replaces_the_old_one(self, client, headers):
        first = say(client, headers, "I need trekking shoes under 20000")
        assert first["plan_id"], first

        second = say(client, headers, "mobile", first["session_id"])
        reply = second["assistant_message"].lower()
        assert "shoe" not in reply and "trek" not in reply, (
            f"asking about a mobile was answered with the shoes: {reply[:200]}"
        )
        assert second["slots"]["goal_text"] == "mobile", second["slots"]

    def test_the_old_budget_does_not_follow_the_new_subject(self, client, headers):
        """Rs 20,000 was a ceiling for shoes, not a standing preference.

        Its persistence is what the bug report actually described.
        """
        first = say(client, headers, "I need trekking shoes under 20000")
        second = say(client, headers, "headphones", first["session_id"])
        assert second["slots"].get("budget_total") != 20000, second["slots"]
        assert "20,000" not in second["assistant_message"]

    def test_a_budget_tweak_is_not_a_new_subject(self, client, headers):
        """The mirror image: "under 3000" names nothing, so it must refine the
        shoes rather than become the search query."""
        first = say(client, headers, "I need trekking shoes under 20000")
        second = say(client, headers, "under 3000", first["session_id"])
        assert "trekking shoes" in second["slots"]["goal_text"].lower(), second["slots"]
        assert second["slots"]["budget_total"] == 3000, second["slots"]

    def test_a_goal_plan_survives_a_refinement(self, client, headers, winter_trek_plan):
        """Words the plan already covers refine it; they do not replace it."""
        _, turn1, _turn2 = winter_trek_plan
        body = say(client, headers, "something warmer than that jacket", turn1["session_id"])
        assert body["state"].upper() in ("REFINING", "PRESENTED"), body["state"]


class TestHonestyAboutWhatWeDoNotStock:
    """ADR-004: the catalog is curated. It contains no phones, and saying so is
    the only honest answer -- ranking the whole catalog for "mobile" produced a
    thermal base layer presented as the best match."""

    @pytest.mark.parametrize("message", ["mobile", "smartphone", "refrigerator"])
    def test_unstocked_products_are_refused_not_substituted(
        self, client, headers, message
    ):
        body = say(client, headers, message)
        assert body["plan_id"] is None, (
            f"{message!r} produced a plan from a catalog that has none: "
            f"{body['assistant_message'][:200]}"
        )
        assert "do not have" in body["assistant_message"].lower(), (
            body["assistant_message"][:200]
        )

    def test_the_refusal_says_what_we_do_have(self, client, headers):
        body = say(client, headers, "mobile")
        assert "electronics" in body["assistant_message"].lower(), (
            "a dead end with no way forward: " + body["assistant_message"][:200]
        )

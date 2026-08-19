"""Record real API responses as frontend fixtures.

    python -m scripts.capture_fixtures

Walks the demo journey against the live app and writes each response to
frontend/src/services/mocks/*.json. These back `VITE_USE_MOCKS=true`.

Why record rather than hand-write: a hand-written fixture drifts from the
contract silently, and the first time anyone notices is on stage. A recorded
one is by construction exactly what the API returns today. Re-run this
whenever the contract changes.

Nothing here is a substitute for the real backend during judging -- mock mode
is the fallback if the service is unreachable, and the UI labels it as such.
"""

from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app

OUT = Path(__file__).resolve().parents[2] / "frontend" / "src" / "services" / "mocks"

SESSION_ID = str(uuid.uuid4())
HEADERS = {"X-Session-Id": SESSION_ID}
ADMIN = {"X-Admin-Token": settings.ADMIN_TOKEN}

DEMO = ("I'm going for a 4-day winter trek in Manali, budget Rs 15,000, "
        "I'm a beginner, I already have trekking shoes and a backpack")

written: list[tuple[str, int]] = []


def dump(name: str, payload: Any) -> None:
    path = OUT / f"{name}.json"
    text = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    path.write_text(text, encoding="utf-8")
    written.append((f"{name}.json", len(text)))


def ok(response) -> Any:
    if response.status_code != 200:
        raise AssertionError(
            f"{response.request.method} {response.request.url.path} -> "
            f"{response.status_code}: {response.text[:300]}"
        )
    return response.json()


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)

    with TestClient(app) as client:
        print("Capturing fixtures...")

        # ---- wave 1 -------------------------------------------------------
        dump("health", ok(client.get("/api/health")))

        search = ok(client.get(
            "/api/products/search",
            params={"q": "winter trekking jacket", "sort": "relevance", "page_size": 20},
            headers=HEADERS,
        ))
        dump("products_search", search)
        dump("product_detail", ok(client.get(
            f"/api/products/{search['items'][0]['id']}", headers=HEADERS)))

        # ---- wave 2: the two-turn demo conversation ------------------------
        turn1 = ok(client.post("/api/chat",
                               json={"session_id": None, "message": DEMO},
                               headers=HEADERS))
        dump("chat_turn1", turn1)

        turn2 = ok(client.post("/api/chat",
                               json={"session_id": turn1["session_id"],
                                     "message": "Camping overnight"},
                               headers=HEADERS))
        dump("chat_turn2", turn2)

        plan_id = turn2["plan_id"]
        if not plan_id:
            raise AssertionError("the demo conversation produced no plan")

        dump("session", ok(client.get(f"/api/session/{turn1['session_id']}",
                                      headers=HEADERS)))

        # ---- wave 3 -------------------------------------------------------
        dump("requirements", ok(client.get(f"/api/requirements/{plan_id}",
                                           headers=HEADERS)))

        recommendations = ok(client.post("/api/recommendations",
                                         json={"plan_id": plan_id,
                                               "requirement_ids": None,
                                               "limit_per_requirement": 5},
                                         headers=HEADERS))
        dump("recommendations", recommendations)

        # ---- wave 4 -------------------------------------------------------
        dump("bundle_optimize", ok(client.post(
            "/api/bundle/optimize",
            json={"plan_id": plan_id,
                  "presets": ["best_overall", "best_budget", "premium"],
                  "include_priorities": ["essential", "recommended", "optional"]},
            headers=HEADERS)))

        plan = ok(client.get(f"/api/shopping-plan/{plan_id}", headers=HEADERS))
        dump("shopping_plan", plan)

        # ---- wave 5: explain + compare on a real recommendation ------------
        first = next(r for r in recommendations["results"] if r["recommendations"])
        requirement_id = first["requirement"]["id"]
        picks = first["recommendations"]

        dump("explain", ok(client.post(
            "/api/explain",
            json={"product_id": picks[0]["product"]["id"],
                  "requirement_id": requirement_id,
                  "plan_id": plan_id},
            headers=HEADERS)))

        dump("compare", ok(client.post(
            "/api/compare",
            json={"product_ids": [p["product"]["id"] for p in picks[:4]],
                  "plan_id": plan_id},
            headers=HEADERS)))

        # ---- wave 6 -------------------------------------------------------
        ok(client.post("/api/feedback",
                       json={"product_id": picks[0]["product"]["id"],
                             "plan_id": plan_id,
                             "feedback_type": "saved",
                             "comment": None},
                       headers=HEADERS))
        dump("profile", ok(client.get("/api/profile", headers=HEADERS)))
        dump("admin_metrics", ok(client.get("/api/admin/metrics", headers={**HEADERS, **ADMIN})))
        dump("audit_logs", ok(client.get("/api/admin/audit-logs",
                                         params={"limit": 60},
                                         headers={**HEADERS, **ADMIN})))

    print(f"\nWrote {len(written)} fixtures to {OUT}:")
    for name, size in written:
        print(f"  {name:24} {size / 1024:6.1f} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

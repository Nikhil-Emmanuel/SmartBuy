# SmartBuy AI — API Contract (FROZEN v1.0)

**This document is the interface between Member 6/7 (backend) and Member 7 (frontend). Once frozen,
the frontend builds against it with mocks and the backend fills it in. Neither waits for the other.**

Base URL: `${VITE_API_BASE_URL}` → `http://localhost:8000` in dev.
All requests/responses `application/json`. Money is **integer rupees**. Scores are floats `0.0–1.0`.
Session identity travels in the `X-Session-Id` header (UUID4 minted by the client on first load).

---

## Conventions

**Error envelope** — every 4xx/5xx:
```json
{ "error": { "code": "BUDGET_INFEASIBLE", "message": "Human-readable.", "details": {} } }
```
Codes: `VALIDATION_ERROR` · `SESSION_NOT_FOUND` · `PLAN_NOT_FOUND` · `PRODUCT_NOT_FOUND` ·
`BUDGET_INFEASIBLE` · `NO_PRODUCTS_FOUND` · `LLM_UNAVAILABLE` · `RATE_LIMITED` · `INTERNAL_ERROR`

**`LLM_UNAVAILABLE` is never returned to the user for a chat turn** — the deterministic fallback
handles it and the response carries `"degraded": true` instead.

---

## Shared objects

### `Product`
```json
{
  "id": "3f2a...", "source": "MARKET_A", "name": "Wildcraft Thermal Base Layer",
  "brand": "Wildcraft", "category": "clothing", "subcategory": "thermals",
  "price": 1299, "original_price": 1799, "discount_pct": 28,
  "rating": 4.5, "review_count": 2841,
  "features": ["thermal", "quick_dry", "lightweight"],
  "availability": "in_stock", "delivery_days": 2,
  "url": "https://...", "image_url": "https://...",
  "tags": ["winter", "trekking", "beginner"], "is_simulated": true
}
```

### `ScoreBreakdown` — powers Page 7, never omitted from a recommendation
```json
{
  "goal_suitability": 0.94, "preference_match": 0.72, "quality": 0.90,
  "feature_match": 0.85, "budget_fit": 0.95, "review_strength": 0.88,
  "delivery": 0.80, "deal_value": 0.70, "final": 0.87
}
```

### `Recommendation`
```json
{
  "product": { ...Product },
  "requirement_id": "req_...", "score": 0.87, "rank": 1,
  "badge": "best_overall",
  "score_breakdown": { ...ScoreBreakdown },
  "reasons": ["Rated for sub-zero conditions", "28% below list price", "Arrives in 2 days"],
  "offer": { "offer_type": "discount", "discount_pct": 28, "coupon_code": null }
}
```
`badge ∈ best_overall | best_budget | best_rated | best_premium | best_deal | null`

### `Requirement`
```json
{
  "id": "req_...", "item_name": "Thermal Base Layer",
  "category": "clothing", "subcategory": "thermals",
  "priority": "essential", "quantity": 2,
  "reason": "Traps body heat in sub-12°C conditions.",
  "est_price_min": 800, "est_price_max": 2500,
  "is_owned": false, "fulfillment_status": "fulfilled"
}
```

### `Slots`
```json
{
  "goal_text": "4-day winter trek in Manali", "activity": "winter_trek",
  "location": "Manali", "region_type": "mountain", "season": "winter",
  "duration_days": 4, "people_count": 1, "experience_level": "beginner",
  "budget_total": 15000, "currency": "INR", "camping": null,
  "existing_items": ["trekking shoes", "backpack"],
  "preferences": { "brands": [], "price_bias": "balanced", "delivery_bias": "standard" }
}
```

---

## 1. Chat — the spine of the application

### `POST /api/chat`
```json
{ "session_id": "uuid|null", "message": "I'm going for a 4-day winter trek in Manali. Budget ₹15,000, I'm a beginner and I already have shoes and a backpack." }
```

**200**
```json
{
  "session_id": "uuid",
  "state": "SLOT_FILL",
  "intent": "GOAL_BASED_SHOPPING",
  "assistant_message": "Got it — a 4-day winter trek in Manali on a ₹15,000 budget. One thing I need to know: are you camping overnight, or staying in guesthouses?",
  "chips": ["Camping overnight", "Guesthouses", "Not sure yet"],
  "slots": { ...Slots },
  "collected": ["location", "duration_days", "budget_total", "experience_level", "existing_items"],
  "missing": ["camping"],
  "assumptions": [ { "slot": "season", "value": "winter", "basis": "Manali in December" } ],
  "progress": 0.7,
  "plan_id": null,
  "next_action": "answer_question",
  "degraded": false
}
```
`next_action ∈ answer_question | view_requirements | view_plan | none` — the frontend uses this to
decide whether to render a reply box or a "See what you need →" CTA. **Do not infer navigation from
`state` in the UI; use `next_action`.**

When slot filling completes the same endpoint returns `state: "PLANNING"`, a populated `plan_id`,
and `next_action: "view_requirements"`.

### `GET /api/session/{session_id}`
Returns `{ session_id, state, slots, intent, messages[], plan_id }`. Powers refresh-survival.

### `POST /api/session/{session_id}/slots`
Manual slot correction from the sidebar: `{ "budget_total": 20000 }` → returns the updated session.
Editing a slot after `PRESENTED` marks the plan stale and re-runs discovery.

---

## 2. Requirements

### `POST /api/requirements/generate`
`{ "session_id": "uuid" }` → generates from the KB + slots, persists a `shopping_plan`.

**200**
```json
{
  "plan_id": "plan_...",
  "goal": "4-day winter trek in Manali",
  "goal_summary": "Beginner-friendly winter trek kit for 4 days in the Himalayas, under ₹15,000.",
  "context": { ...Slots },
  "requirements": {
    "essential":   [ ...Requirement ],
    "recommended": [ ...Requirement ],
    "optional":    [ ...Requirement ]
  },
  "already_owned": [ { "item_name": "Trekking Shoes", "matched_from": "trekking shoes" } ],
  "estimated_range": { "min": 8400, "max": 16200 }
}
```

### `GET /api/requirements/{plan_id}` — same payload, re-fetch.
### `PATCH /api/requirements/{requirement_id}` — `{ "is_owned": true }` or `{ "quantity": 2 }`. Marks the plan stale.

---

## 3. Products

### `GET /api/products/search`
Query: `q` · `category` · `subcategory` · `brand` · `min_price` · `max_price` · `min_rating` ·
`source` · `features` (csv) · `sort` (`relevance|price_asc|price_desc|rating|delivery|deal`) ·
`page` · `page_size` (default 20, max 50)

**200** `{ "items": [ ...Product ], "total": 137, "page": 1, "page_size": 20, "facets": { "brands": {...}, "sources": {...}, "price_buckets": [...] } }`

### `GET /api/products/{id}` → `Product` + `offers[]` + `other_sources[]` (same `product_group_key`, different marketplace — this is the cross-marketplace price row).

---

## 4. Recommendations & comparison

### `POST /api/recommendations`
```json
{ "plan_id": "plan_...", "requirement_ids": ["req_..."] | null, "limit_per_requirement": 5 }
```
**200**
```json
{
  "plan_id": "plan_...",
  "results": [
    { "requirement": { ...Requirement },
      "recommendations": [ ...Recommendation ],
      "unfulfilled_reason": null }
  ]
}
```
`requirement_ids: null` ⇒ all requirements. `unfulfilled_reason ∈ no_candidates | all_over_budget | all_out_of_stock | null`.

### `POST /api/compare`
`{ "product_ids": ["...", "..."], "plan_id": "plan_...|null" }`
**200** — table-shaped so the frontend renders it without transformation:
```json
{
  "columns": ["price","rating","review_count","delivery_days","match_score","deal_value","availability"],
  "rows": [ { "product": {...Product}, "match_score": 0.87, "deal_value": 0.7,
              "score_breakdown": {...}, "is_best": { "price": false, "rating": true } } ],
  "winner": { "best_overall": "id", "best_budget": "id", "best_rated": "id",
              "best_premium": "id", "best_deal": "id" }
}
```

### `POST /api/explain`
`{ "product_id": "...", "requirement_id": "...", "plan_id": "..." }`
```json
{
  "match_score": 0.91,
  "score_breakdown": { ...ScoreBreakdown },
  "weighted_points": [ { "label": "Goal suitability", "earned": 23.5, "max": 25 },
                       { "label": "Budget fit", "earned": 19.0, "max": 20 } ],
  "summary": "This is the strongest all-round pick for a beginner's winter trek at your budget.",
  "reasons": ["Rated to -5°C, appropriate for Manali in winter", "..."],
  "evidence": { "rating": 4.5, "review_count": 2841, "price": 1299, "delivery_days": 2 }
}
```
`weighted_points` sums to 100 — this is the Page 7 scorecard. **The `summary` is LLM prose but every
number in `weighted_points` and `evidence` is computed in Python.**

---

## 5. Bundle optimization

### `POST /api/bundle/optimize`
`{ "plan_id": "plan_...", "presets": ["best_overall","best_budget","premium"], "include_priorities": ["essential","recommended"] }`

**200**
```json
{
  "plan_id": "plan_...", "budget": 15000,
  "bundles": [
    {
      "preset": "best_overall", "total_cost": 12450, "total_savings": 1850,
      "remaining_budget": 2550, "utility_score": 0.86, "requirement_coverage": 1.0,
      "items": [ { "requirement": {...}, "product": {...Product},
                   "quantity": 1, "line_total": 1299, "score": 0.87, "reasons": [...] } ],
      "excluded": [ { "requirement_id": "req_...", "reason": "optional, budget prioritized to essentials" } ]
    }
  ],
  "substitutions": [
    { "requirement_id": "req_...", "from": {...Product}, "to": {...Product},
      "price_delta": -1700, "score_delta": -0.04,
      "reason": "Saves ₹1,700 with nearly identical insulation rating, bringing the bundle under budget." }
  ],
  "infeasible": false,
  "shortfall": null
}
```
When essentials alone exceed budget: `"infeasible": true`, `"shortfall": 2300`, and `bundles`
still contains the essentials-only bundle so the user sees something actionable. Master prompt §54.

### `POST /api/substitute`
`{ "plan_id": "...", "requirement_id": "...", "current_product_id": "...", "reason": "cheaper|better_rated|faster_delivery|unavailable" }`
→ `{ "alternatives": [ { "product": {...}, "price_delta": -1700, "score_delta": -0.04, "why": "..." } ] }`

### `POST /api/bundle/select` — `{ "plan_id": "...", "preset": "best_overall" }` persists the choice.

---

## 6. Plan, feedback, profile

### `GET /api/shopping-plan/{plan_id}` — **the Page 6 payload.** Everything in one call:
```json
{
  "plan_id": "...", "goal": "...", "goal_summary": "...", "status": "complete",
  "context": { ...Slots },
  "requirements": { "essential": [...], "recommended": [...], "optional": [...] },
  "already_owned": [...],
  "bundles": [ ...Bundle ], "selected_preset": "best_overall",
  "totals": { "budget": 15000, "estimated_total": 12450, "savings": 1850, "remaining": 2550 },
  "substitutions": [...],
  "unfulfilled": [ { "requirement_id": "...", "item_name": "...", "reason": "no_candidates" } ]
}
```

### `POST /api/feedback`
`{ "product_id": "...", "plan_id": "...", "feedback_type": "relevant|not_relevant|saved|not_interested", "comment": null }`
→ `{ "ok": true, "preferences_updated": true, "updated_preferences": { ...UserPreferences } }`

### `GET /api/profile` · `PUT /api/profile`
```json
{
  "user_id": "...", "is_anonymous": true,
  "preferences": { "preferred_categories": ["outdoor","electronics"],
                   "preferred_brands": ["Wildcraft"],
                   "min_price": 1500, "max_price": 5000,
                   "price_bias": "value", "delivery_bias": "fast" },
  "saved_products": [ ...Product ],
  "recent_plans": [ { "plan_id": "...", "goal": "...", "estimated_total": 12450, "created_at": "..." } ],
  "feedback_history": [ { "product": {...}, "feedback_type": "relevant", "created_at": "..." } ]
}
```

### `GET /api/offers?product_ids=a,b,c` → `{ "offers": { "<product_id>": [ ...Offer ] } }`

---

## 7. Admin — header `X-Admin-Token: ${ADMIN_TOKEN}`

### `GET /api/admin/metrics`
```json
{
  "users": 42, "sessions": 118, "plans_generated": 97,
  "recommendations_generated": 1544, "avg_bundle_value": 11890,
  "budget_compliance_rate": 0.94, "requirement_coverage_avg": 0.91,
  "feedback": { "relevant": 210, "not_relevant": 38, "saved": 64, "not_interested": 12 },
  "recommendation_acceptance_rate": 0.85,
  "llm": { "calls": 402, "failures": 3, "fallback_rate": 0.007, "avg_latency_ms": 780 },
  "top_categories": [ { "category": "clothing", "count": 310 } ]
}
```
Every number here is a real aggregate query. **No hard-coded demo values in the admin dashboard.**

### `GET /api/admin/audit-logs?limit=100&session_id=&action=`
→ `{ "logs": [ { "id","session_id","action","tool","input_summary","output_summary","model_version","latency_ms","status","created_at" } ], "total": 1204 }`

### `GET /api/health` → `{ "status": "ok", "db": "ok", "llm": "ok|degraded", "catalog_size": 3012 }`
Public, no auth. Check this first on stage.

---

## Build order for the API (backend follows this exact sequence)

| Wave | Endpoints | Unblocks |
|---|---|---|
| 1 | `/api/health`, `/api/products/search`, `/api/products/{id}` | Frontend product surfaces immediately |
| 2 | `/api/chat`, `/api/session/{id}` | The entire demo spine |
| 3 | `/api/requirements/generate`, `/api/recommendations` | Pages 3 & 4 |
| 4 | `/api/bundle/optimize`, `/api/shopping-plan/{id}` | Page 6 — the money shot |
| 5 | `/api/explain`, `/api/compare`, `/api/substitute` | Pages 5 & 7 |
| 6 | `/api/feedback`, `/api/profile`, `/api/admin/*` | Pages 8 & 9 |

Frontend codes against `frontend/src/services/mocks/*.json` — fixtures matching this contract
exactly, committed in wave 0 — and flips a single `USE_MOCKS` flag per wave as endpoints land.

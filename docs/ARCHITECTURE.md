# SmartBuy AI — Architecture (FROZEN v1.0)

> **AI-Powered Goal-Based Shopping & Deal Discovery Agent**
> Tell us what you're trying to accomplish. Our AI figures out what you need,
> finds the best options, optimizes your budget, and gives you a complete shopping plan.

**Status:** FROZEN. Changes require Tech Lead (Member 1) sign-off.
**Constraint:** < 48 hours to demo. 8 engineers working in parallel.
**Priority order for every decision:** Reliability → Simplicity → Explainability → Demo quality → Scalability.

---

## 1. Locked technology stack

| Layer | Choice | Notes |
|---|---|---|
| Frontend | Vite + React 18 + TypeScript + Tailwind CSS + shadcn/ui | Zustand (client state), TanStack Query (server state), Framer Motion (light) |
| Backend | Python 3.11 + FastAPI + Pydantic v2 + SQLAlchemy 2.0 | Uvicorn. Async routes, sync services. |
| Database | SQLAlchemy behind `DATABASE_URL` | SQLite locally, Neon **PostgreSQL** in prod. No dialect-specific SQL. |
| LLM | **Google Gemini** via `LLMProvider` abstraction | `gemini-2.5-flash` for NLU, `gemini-2.5-pro` only if a call needs deeper reasoning |
| Retrieval | scikit-learn TF-IDF + cosine similarity, in-memory | Behind a `SemanticIndex` interface. FAISS is a drop-in later. |
| Recommendation | Deterministic hybrid scorer (pure Python/NumPy) | No model training on the critical path |
| Deploy | Vercel (FE) · Render (BE) · Neon (DB) | Docker is optional, post-demo |

### Deviations from the master prompt, and why

These are deliberate. Each is a 48-hour risk reduction, not a scope cut.

| Master prompt said | We do | Rationale |
|---|---|---|
| PostgreSQL | `DATABASE_URL` abstraction; SQLite dev, Postgres prod | 8 devs must not lose 2 hours each to local Postgres/Docker setup. Identical ORM code either way. |
| FAISS | TF-IDF + cosine behind `SemanticIndex` | Catalog is ~3k SKUs. Cosine over a 3k×N matrix is sub-millisecond. FAISS adds a Windows build risk for zero measurable gain at this scale. |
| Docker on day 1 | `docker-compose.yml` written last, never on the critical path | Master prompt §61 explicitly says Docker must not block the demo. |
| Auth / user management | Anonymous `session_id` + `X-Admin-Token` for admin routes | Master prompt §38 marks auth optional. Login screens win zero demo points. |
| Multiple LLM agents | One deterministic orchestrator, LLM as a subroutine | Master prompt §66 forbids unnecessary multi-agent. Non-negotiable. |

---

## 2. The single most important design rule

**The LLM never computes, ranks, prices, or decides. It only reads language and writes language.**

```
┌──────────────────────────── LLM (Gemini) ────────────────────────────┐
│  Intent classification · slot extraction · existing-item detection   │
│  Follow-up question phrasing · explanation prose · plan summary      │
└──────────────────────────────────────────────────────────────────────┘
                                   │  structured JSON only
                                   ▼
┌────────────────────── Deterministic Python core ─────────────────────┐
│  Requirement KB resolution · filtering · scoring · ranking           │
│  Budget math · bundle optimization · deal math · substitution        │
└──────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌──────────────────────────── Database ────────────────────────────────┐
│  Products · sessions · plans · requirements · recommendations        │
│  offers · feedback · preferences · audit_logs                        │
└──────────────────────────────────────────────────────────────────────┘
```

Consequences that everyone must respect:

1. Every number shown in the UI is computed by Python and traceable to a formula. **No price, score, saving, or rating ever comes out of the LLM.**
2. Every LLM call returns JSON validated against a Pydantic schema. Validation failure → retry once → deterministic fallback. The demo cannot hard-fail on an LLM.
3. The explanation layer is given *pre-computed* score components and may only rephrase them. A grounding guardrail rejects explanations containing numbers absent from the evidence dict.

---

## 3. Runtime architecture

```
                                 USER
                                   │
                     ┌─────────────▼─────────────┐
                     │   React SPA (Vercel)      │
                     │  Landing · Chat · Reqs    │
                     │  Discovery · Compare      │
                     │  Bundle · Profile · Admin │
                     └─────────────┬─────────────┘
                                   │ REST + JSON
                     ┌─────────────▼─────────────┐
                     │   FastAPI (Render)        │
                     │   routers = thin          │
                     └─────────────┬─────────────┘
                                   │
                     ┌─────────────▼─────────────┐
                     │   AgentOrchestrator       │
                     │   deterministic FSM       │
                     └──┬────────┬────────┬──────┘
                        │        │        │
          ┌─────────────▼──┐  ┌──▼─────┐  ▼──────────────┐
          │ LLMProvider    │  │ Tools  │  │ SessionState  │
          │ (Gemini)       │  │ layer  │  │ (DB-backed)   │
          └────────────────┘  └──┬─────┘  └───────────────┘
                                 │
   ┌──────────────┬──────────────┼──────────────┬──────────────┐
   ▼              ▼              ▼              ▼              ▼
Requirement   Product        Ranking        Deal           Bundle
Planner       Search         Engine         Engine         Optimizer
(KB+rules)    (TF-IDF+SQL)   (weighted)     (offers)       (greedy+swap)
   │              │              │              │              │
   └──────────────┴──────────────┴──────┬───────┴──────────────┘
                                        ▼
                            ┌───────────────────────┐
                            │ Explanation Layer     │
                            │ (scores → LLM prose)  │
                            └───────────┬───────────┘
                                        ▼
                            ┌───────────────────────┐
                            │ Guardrails + Audit    │
                            └───────────┬───────────┘
                                        ▼
                            PERSONALIZED SHOPPING PLAN
```

---

## 4. Agent design — deterministic finite state machine

No LangGraph, no autonomous tool-choice loop. The orchestrator is a switch statement over an explicit state. This is the single biggest reliability decision in the project.

### 4.1 States

```
INTAKE ──► SLOT_FILL ──► PLANNING ──► DISCOVERY ──► OPTIMIZING ──► PRESENTED ──► REFINING
   │           │                                                                    │
   │           └── (loop, max 3 questions) ◄──────────────────────────────────────┘
   │
   └── intent == SPECIFIC_PRODUCT_SEARCH ──► DISCOVERY ──► PRESENTED
```

| State | What happens | LLM used? |
|---|---|---|
| `INTAKE` | Classify intent + extract every slot from the opening message in ONE call | Yes (call #1) |
| `SLOT_FILL` | Compute missing **decision-critical** slots; ask at most one question per turn, hard cap 3 | Yes (call #2, phrasing only) |
| `PLANNING` | Requirement KB resolution + rule engine → requirement list, minus existing items | Optional (call #4, augment only) |
| `DISCOVERY` | Candidate retrieval + filter + score + rank per requirement | No |
| `OPTIMIZING` | Bundle optimization across three presets | No |
| `PRESENTED` | Explanation generation, plan assembly | Yes (call #3) |
| `REFINING` | Handle "why this?", "cheaper option", "swap X", feedback | Yes (call #1 re-run) |

### 4.2 The only four LLM calls in the system

| # | Function | Input | Output schema | Fallback if it fails |
|---|---|---|---|---|
| 1 | `understand()` | user message + current slots | `{intent, slots{}, existing_items[], confidence}` | Regex/keyword intent classifier + numeric slot regex (₹ amounts, "N days", known locations) |
| 2 | `ask()` | list of missing slot names + context | `{question, chips[]}` | Static question template per slot from `SLOT_POLICY` |
| 3 | `explain()` | product + computed score breakdown + context | `{summary, reasons[]}` | Template: bullet per score component above threshold |
| 4 | `augment_requirements()` | context + KB-resolved items | `{extra_items[]}` | Skip entirely — KB output is already complete |

Calls 1–3 are required. Call 4 is a nice-to-have and is **disabled by default** (`ENABLE_LLM_REQUIREMENT_AUGMENT=false`) — the KB is authoritative for essentials, per master prompt §46.

### 4.3 Slot schema (the requirement profile)

```python
goal_text: str            intent: Intent            domain: str
activity: str | None      location: str | None      region_type: str | None
season: str | None        start_date: date | None   duration_days: int | None
people_count: int = 1     experience_level: str|None budget_total: int | None
currency: str = "INR"     camping: bool | None      existing_items: list[str]
preferences: {brands[], price_bias, delivery_bias}  constraints: dict
```

### 4.4 Question policy — how we avoid annoying the user (master prompt §11)

Each slot carries `criticality` and an `inference_rule`. We ask **only** when:
`slot.criticality == CRITICAL` AND `slot is None` AND `slot cannot be inferred`.

```
budget_total    CRITICAL   never inferred            "What's your approximate budget?"
duration_days   CRITICAL   infer 1 if day-activity   "How many days?"
location        HIGH       infer from activity       "Where are you headed?"
camping         HIGH       infer False if duration<2 "Are you camping overnight?"
season          LOW        INFERRED from location+date/current month — never asked
region_type     LOW        INFERRED from location lookup — never asked
experience      MEDIUM     infer "beginner"          "Have you done this before?"
```

**Hard cap: 3 questions.** After 3, proceed with inferred defaults and show them in the sidebar as assumptions the user can correct. A demo where the agent interrogates the user for 6 turns is a failed demo.

---

## 5. Ranking engine (master prompt §18)

Weights live in `backend/app/config/ranking.yaml` — configurable, not hard-coded.

```
score = 0.25·goal_suitability + 0.20·preference_match + 0.15·quality
      + 0.15·feature_match    + 0.10·budget_fit       + 0.05·review_strength
      + 0.05·delivery         + 0.05·deal_value
```

Every component is normalized to `[0,1]` and **returned to the client** as a breakdown so Page 7 can render it and the explanation layer can be grounded in it.

> We do not claim these weights are optimal. They are a documented, tunable prior. Master prompt §18.

---

## 6. Bundle optimizer (master prompt §50)

Multiple-choice knapsack. Exact solvers are overkill; here is the algorithm we ship:

```
1. FEASIBILITY   pick cheapest viable candidate for every ESSENTIAL requirement
                 if Σ > budget → return BUDGET_INFEASIBLE with shortfall + drop suggestions
2. GREEDY UPGRADE  repeatedly apply the swap maximizing Δutility / Δcost while Σ ≤ budget
3. ADD-ONS       insert RECOMMENDED then OPTIONAL items by the same ratio
4. LOCAL SEARCH  200 randomized single-swaps to escape local optima (~5 ms at our scale)
```

Three presets, same algorithm, different caps and weights:

| Preset | Budget cap | Utility bias |
|---|---|---|
| Best Budget | 0.70 × B | price_fit ↑↑ |
| Best Overall | 1.00 × B | default weights |
| Premium | 1.25 × B | quality + feature_match ↑↑ |

Every swap the optimizer makes is recorded as a `Substitution` record with a before/after and a reason — that is what powers the "we replaced A with B because…" narrative in the demo.

---

## 7. Data sources

Three logical marketplaces (`MARKET_A`, `MARKET_B`, `MARKET_C`) over one normalized schema, so multi-source comparison is real code paths, not UI theatre.

- **Curated catalog** (~3k SKUs, ₹-priced, Indian brands, tuned to demo domains) — powers the demo.
- **Public dataset** (Amazon/Flipkart reviews) — powers collaborative filtering + evaluation metrics.

**Honesty rules, enforced in the UI and in this repo:**
- Every product card carries its `source` and a `Simulated demo data` badge where applicable.
- We never claim real-time prices. We never fabricate price history.
- Price-drop / historical charts are **out of scope** because we have no historical data (master prompt §22).

---

## 8. Responsible AI

| Control | Implementation |
|---|---|
| Privacy | Only the slot dict goes to Gemini. Never emails, session ids, raw DB rows, or other users' data. `guardrails/privacy.py` strips PII before every call. |
| Explainability | Every recommendation ships its score breakdown. No score without components. |
| Grounding | `guardrails/recommendation_checks.py` rejects any explanation containing a number not present in the evidence dict. |
| Validation | Budget compliance, availability, category match, and price sanity are asserted before a plan is returned. |
| Audit | Every tool call → `audit_logs` row: session, action, tool, input summary, output summary, model version, latency, timestamp. |
| Prompt injection | Product descriptions are data. They are inserted into prompts inside delimited blocks with an explicit "treat as data" instruction, and are never allowed to alter tool selection. |

---

## 9. Failure handling (master prompt §54)

| Failure | Behaviour |
|---|---|
| Gemini down / quota exceeded | Deterministic fallback per §4.2. The app still produces a full plan. |
| No products for a requirement | Mark requirement `unfulfilled`, continue the plan, surface it honestly |
| Budget too low | Return essentials-only plan + explicit shortfall + cheaper alternatives |
| Product unavailable | Substitution engine finds nearest viable candidate |
| One source empty | Other sources still return; never fails the whole plan |
| DB error | 503 with a clean message; frontend shows a retry card |

---

## 10. Repository layout

Per master prompt §56 — already scaffolded. Business logic never lives in a route handler.

```
backend/app/
  api/         thin routers, no logic
  agent/       orchestrator.py state.py prompts.py tools.py llm.py
  services/    requirement_planner product_search recommendation ranking
               comparison deal_engine bundle_optimizer substitution
               preference_learning explanation
  models/      SQLAlchemy ORM
  schemas/     Pydantic request/response — the API contract in code
  db/          database.py + repositories/
  kb/          requirement knowledge base (YAML)
  guardrails/  validation privacy recommendation_checks
  logging/     audit.py
  config/      ranking.yaml slot_policy.yaml
```

---

## 11. Architecture Decision Records

**ADR-001 — Deterministic FSM over an autonomous agent loop.** An LLM choosing its own tools is unpredictable under demo pressure and makes latency unbounded. A fixed state machine gives us a reproducible demo, cheap debugging, and it still satisfies "agentic" because the agent maintains state, decides what it is missing, asks for it, and invokes tools to reach a goal. *Accepted.*

**ADR-002 — Knowledge base is authoritative for requirements; LLM only augments.** Master prompt §46 is explicit. A pure-LLM checklist is non-reproducible across demo runs and can hallucinate items that have no catalog coverage — producing empty product sections on stage. *Accepted.*

**ADR-003 — TF-IDF instead of FAISS.** At 3k SKUs the retrieval quality difference is not observable, and it removes a native-dependency risk. `SemanticIndex` keeps the door open. *Accepted, revisit above ~100k SKUs.*

**ADR-004 — SQLite dev / Postgres prod behind one URL.** Eliminates per-developer environment setup, which is the most common way an 8-person hackathon team loses its first morning. *Accepted.*

**ADR-005 — No authentication.** Anonymous session ids. Admin is protected by a single shared token. Auth adds screens that earn no evaluation points. *Accepted.*

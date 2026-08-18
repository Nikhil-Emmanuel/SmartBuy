# SmartBuy AI

### AI-Powered Goal-Based Shopping & Deal Discovery Agent

> **Tell us what you're trying to accomplish. Our AI figures out what you need, finds the best
> options, optimizes your budget, and gives you a complete shopping plan.**

---

## The problem

Every e-commerce search engine assumes you already know what to buy. Type "trekking jacket" and
you get trekking jackets. But if you're a beginner planning your first 4-day winter trek in Manali,
your real problem isn't finding a jacket — it's that **you don't know what the full list is**, you
don't know what's worth the money, and you don't know how to fit all of it into ₹15,000.

Existing recommenders are product-centric. They optimize *"which item is most similar to what you
just viewed."* Nobody optimizes *"what is the complete set of things this person needs to accomplish
their goal, and what is the best possible basket within their budget."*

## What SmartBuy AI does

```
"I'm going for a 4-day winter trek in Manali. I'm a beginner,
 my budget is ₹15,000, and I already have shoes and a backpack."
                          ↓
   understand goal → ask only what's missing → derive the full requirement list
   → subtract what you already own → search 3 marketplaces → rank against your
   context → optimize the whole basket to your budget → explain every choice
                          ↓
     A complete, priced, sourced, explainable shopping plan.
```

It supports both modes:

- **Mode A — you know the product.** *"Waterproof trekking shoes under ₹3,000."* → straight to
  search, comparison and ranking. No interrogation.
- **Mode B — you know the goal.** *"I'm going on a 4-day trek."* → the full planning journey.
  **This is the innovation.**

---

## Architecture in one paragraph

A React SPA talks to a FastAPI backend. A **deterministic agent orchestrator** — a finite state
machine, not an autonomous loop — drives the conversation. Google Gemini is used for exactly four
things: understanding the user's message, phrasing follow-up questions, augmenting requirements, and
writing explanations. **Every number in the product — every price, score, saving and ranking — is
computed in Python and is traceable to a formula.** The LLM never does arithmetic and never picks a
product. This is what makes the system explainable and what makes the demo reproducible.

Full detail: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)

| Document | Contents |
|---|---|
| [ARCHITECTURE.md](docs/ARCHITECTURE.md) | Stack, agent FSM, ranking, optimizer, Responsible AI, ADRs |
| [DATA_MODEL.md](docs/DATA_MODEL.md) | Normalized product schema, all tables, KB format, vocabularies |
| [API_CONTRACT.md](docs/API_CONTRACT.md) | Every endpoint with exact request/response JSON |
| [48H_PLAN.md](docs/48H_PLAN.md) | Hour-by-hour plan, 8-member split, cut lines |

---

## Quickstart

*(Filled in as the modules land — see `docs/48H_PLAN.md` for current status.)*

```bash
# Backend
cd backend && python -m venv .venv && source .venv/Scripts/activate
pip install -r requirements.txt
cp ../.env.example .env        # add your GEMINI_API_KEY
python -m scripts.seed         # loads the curated catalog
uvicorn app.main:app --reload
```

```bash
# Frontend
cd frontend && npm install && npm run dev
```

---

## Honesty about the data

This is a hackathon prototype and we are explicit about what is real:

- The product catalog is a **curated, simulated multi-marketplace dataset** with realistic ₹ pricing.
  Every simulated product is badged as such in the UI.
- We do **not** retrieve real-time marketplace prices, and we do **not** claim to.
- We do **not** show price history or price-drop predictions, because we have no historical price
  data and inventing it would be dishonest.
- Recommendation ranking weights are a documented, tunable prior — not an empirically optimized model.
- Collaborative filtering and evaluation metrics run on a public reviews dataset; reported metrics
  are actual measured results, never estimates.

---

## Out of scope (deliberately)

Browser extension · voice · image input · PDF/itinerary parsing · real-time marketplace APIs ·
price tracking · autonomous purchasing · mobile app. All future scope, none of it built.

---

## Team

Tech Lead · Data Engineering · Recommendation/ML · Requirements & Optimization ·
Agentic AI · Backend · Frontend · Responsible AI/QA/DevOps — 8 members.
See [`docs/48H_PLAN.md`](docs/48H_PLAN.md) for ownership.

AI tooling used in development is documented in [`AI_USAGE.md`](AI_USAGE.md).

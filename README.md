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
machine, not an autonomous loop — drives the conversation. Google Gemini is used for exactly three
things: understanding the user's message, phrasing follow-up questions, and writing explanations.
The requirement checklist comes entirely from the YAML knowledge base — the LLM never adds an item
to it. **Every number in the product — every price, score, saving and ranking — is
computed in Python and is traceable to a formula.** The LLM never does arithmetic and never picks a
product. This is what makes the system explainable and what makes the demo reproducible.

Full detail: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)

| Document | Contents |
|---|---|
| [ARCHITECTURE.md](docs/ARCHITECTURE.md) | Stack, agent FSM, ranking, optimizer, Responsible AI, ADRs |
| [diagrams/architecture.md](docs/diagrams/architecture.md) | System, sequence, pipeline, degradation and deployment diagrams |
| [DATA_MODEL.md](docs/DATA_MODEL.md) | Normalized product schema, all tables, KB format, vocabularies |
| [DATASET.md](docs/DATASET.md) | Actual dataset headers and sample rows for every table we generate |
| [API_CONTRACT.md](docs/API_CONTRACT.md) | Every endpoint with exact request/response JSON |
| [PERSONALIZATION.md](docs/PERSONALIZATION.md) | The trained segment model: features, training, serving, refusals |
| [EVALUATION.md](docs/EVALUATION.md) | Measured ranking metrics, baselines, ablation — and what they do not prove |
| [AI_USAGE.md](AI_USAGE.md) | Where Gemini is and isn't used, guardrails, and AI tooling disclosure |
| [DEPLOYMENT.md](DEPLOYMENT.md) | Vercel + Render + Neon, Docker, pre-demo checklist |
| [48H_PLAN.md](docs/48H_PLAN.md) | Hour-by-hour plan, 8-member split, cut lines |

---

## The machine learning in this project

Most of what looks like "AI" here is deliberately **not** a learned model, and we keep the line
sharp. There is exactly **one trained model** in the system.

| Component | What it actually is | Trained? |
|---|---|---|
| **Shopper-segment classifier** | scikit-learn `RandomForestClassifier` | **Yes** — the only trained model |
| **Retrieval** | `TfidfVectorizer` + cosine similarity ([product_search.py](backend/app/services/product_search.py)) | No — fitted on the catalog at startup, but a vectorizer, not a predictor |
| **Ranking** | 8-component weighted scorer | No — a hand-tuned prior. We never searched the weight space, so we do **not** claim it is optimal |
| **Language** | Google Gemini `gemini-3.1-flash-lite` | No — reads and writes text only; every number is computed in Python |
| **Collaborative filtering** | **Not built.** `ENABLE_COLLABORATIVE_FILTERING` sits in config and is read by no code | No — there is nothing behind the flag |

### The trained model: shopper segments → personalised offers

Predicts which of four shopper segments a user's behaviour looks like, and the application attaches
a coupon or a perk to that prediction.

| | |
|---|---|
| **Algorithm** | `RandomForestClassifier(n_estimators=300, min_samples_leaf=2, class_weight="balanced")` |
| **Classes** | `deal_seeker` · `window_shopper` · `brand_loyal` · `premium_buyer` |
| **Features** | 27 behavioural features per user — event mix, funnel rates, price/discount/quality means, breadth and brand concentration ([app/ml/features.py](backend/app/ml/features.py)) |
| **Training data** | 250 users with ≥ 10 interactions, 75/25 stratified split |
| **Selection** | 5-fold CV on `f1_macro` — random forest **0.925** beat `StandardScaler → LogisticRegression` **0.914** |
| **Baseline** | `DummyClassifier(strategy="stratified")` — measured, not assumed |
| **Result** | **96.8% holdout accuracy**, 0.968 macro F1, against a **17.5%** stratified-guess floor |
| **Train** | `python ml/personalization/train.py` → `segment_classifier.joblib` + `training_report.json` |
| **Serve** | [personalization.py](backend/app/services/personalization.py) → `GET /api/personalization` |
| **Surface** | [PersonalizedOffer.tsx](frontend/src/components/profile/PersonalizedOffer.tsx) on the profile page |

The offer policy lives in [app/ml/segments.py](backend/app/ml/segments.py), **outside** the model,
because policy buried in a model artifact is policy nobody can review. One rule: *discount where a
discount changes the outcome, and not where it only costs margin* — so a `premium_buyer`, who
converts without one, gets free express delivery instead of a price cut.

**The model is allowed to refuse, and does.** Under 10 events → `insufficient_history`. Under 0.55
confidence → `low_confidence`. If the artifact's stored `feature_names` don't match the serving
code exactly → it is rejected outright, because a model fed columns in a different order does not
error, it returns confident nonsense. A missing model file degrades to "no offer" rather than
failing the request. **It never writes to the database** — it proposes; the application decides.

> **Read the accuracy correctly.** The segment labels are generated by `backend/scripts/seed.py`,
> so 96.8% shows the pipeline recovers structure *we ourselves put into the data* — it catches
> feature bugs, leakage and train/serve skew, which is what it is for. It is **not** evidence about
> how real shoppers behave and must not be presented as if it were. The same caveat is written into
> the training report's `caveat` field and the header of `train.py`.

Full detail: [`docs/PERSONALIZATION.md`](docs/PERSONALIZATION.md)

---

## Quickstart

```bash
# Backend — http://localhost:8000/docs
cd backend && python -m venv .venv && source .venv/Scripts/activate
pip install -r requirements.txt
cp ../.env.example .env        # add your GEMINI_API_KEY (optional, see below)
python -m scripts.seed         # loads the curated catalog (~3,075 products)
uvicorn app.main:app --reload
```

```bash
# Frontend — http://localhost:5173
cd frontend && npm install && npm run dev
```

The Vite dev server proxies `/api` to port 8000, so the two run same-origin and CORS
cannot break the local demo.

**`GEMINI_API_KEY` is optional.** Without it the whole journey still completes on the
deterministic path, and every response is marked `degraded: true` so the UI can say so.
That is a tested guarantee, not a hope — see `tests/backend/test_chaos.py`.

### Verify

```bash
python -m pytest                       # 91 tests: contract, 8 scenarios, chaos, security
python ml/evaluation/run_eval.py       # regenerates ml/evaluation/results/
python ml/personalization/train.py     # retrains the shopper-segment model
```

Full stack in Docker with Postgres (mirrors production): `docker compose up --build`.
Deploying: [DEPLOYMENT.md](DEPLOYMENT.md).

---

## Honesty about the data

This is a hackathon prototype and we are explicit about what is real:

- The product catalog is a **curated, simulated multi-marketplace dataset** with realistic ₹ pricing.
  Every simulated product is badged as such in the UI.
- We do **not** retrieve real-time marketplace prices, and we do **not** claim to.
- We do **not** show price history or price-drop predictions, because we have no historical price
  data and inventing it would be dishonest.
- Recommendation ranking weights are a documented, tunable prior — **not** an empirically optimized
  model. We did not search the weight space, so we do not claim the weights are optimal.
- Collaborative filtering is **not implemented**. `ENABLE_COLLABORATIVE_FILTERING` exists as a
  config flag with no code behind it — an earlier version of this README said the feature was
  "implemented but off by default", which was not true.
- There is no online learning. The personalisation model is a file that changes only when someone
  runs `train.py`; nothing learns from live traffic.
- Our one trained model is trained on **synthetic** behaviour, so its 96.8% measures the pipeline,
  not real shoppers — see [the ML section above](#the-machine-learning-in-this-project).
- Reported metrics are actual measured results from `python ml/evaluation/run_eval.py`, never
  estimates. Relevance is derived from the requirement specification, **not** from user behaviour —
  we have no click or purchase logs, so nothing here measures user satisfaction. The evaluation
  also documents where our own scorer *loses* to a plain TF-IDF baseline, and the label leakage
  that makes our headline ranking number an upper bound. See [EVALUATION.md](docs/EVALUATION.md).

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

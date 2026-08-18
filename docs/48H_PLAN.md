# SmartBuy AI — 48-Hour Execution Plan

8 engineers · < 48 hours · one demo that must not fail.

---

## The one thing that matters

At **T+40h** we must be able to run this end to end, twice, without a code change:

> "I'm going for a 4-day winter trek in Manali. I'm a beginner, my budget is ₹15,000, and I already
> have trekking shoes and a backpack."

Everything in this plan is ordered by how directly it serves that sentence. If a task does not serve
it, it happens after T+40h or not at all.

---

## Critical path (everything else is parallel)

```
Catalog seeded ──► Product search ──► Recommendations ──► Bundle optimizer ──► Plan page
      │                                      ▲
      └──► Requirement KB ──► Planner ───────┘
                  ▲
Slot extraction ──┘
```

**The two hard dependencies, and how we break them on hour one:**

1. *Everyone needs the catalog.* → Member 2 ships **500 trekking SKUs in the first 4 hours**, not
   3,000 SKUs in 12. Breadth comes later; the demo domain comes first.
2. *Everyone needs the API.* → The contract is already frozen (`API_CONTRACT.md`) and Member 7 codes
   against committed mock fixtures from hour zero. The frontend never waits for the backend.

---

## Team assignments

| # | Role | Owns | First commit due |
|---|---|---|---|
| 1 | **Tech Lead** | Repo, integration, `main` merges, **plus frontend pair with M7** | T+2h: repo + CI green |
| 2 | **Data Engineer** | Curated catalog, ETL, normalization, offers, vocabulary validation | T+4h: 500 trek SKUs |
| 3 | **ML Engineer** | Ranking engine, TF-IDF index, CF, evaluation metrics | T+8h: ranking service |
| 4 | **Requirements Eng** | KB YAML, planner, condition DSL, existing-item matching, bundle optimizer | T+6h: `winter_trek.yaml` |
| 5 | **Agentic AI Eng** | Orchestrator FSM, Gemini provider, prompts, slot policy, fallbacks | T+6h: `/api/chat` intent |
| 6 | **Backend Eng** | FastAPI app, models, repositories, all routers, DB | T+3h: `/api/health` + models |
| 7 | **Frontend Eng** | React app, all surfaces, design system | T+3h: landing + chat shell |
| 8 | **RAI / QA / DevOps** | Guardrails, audit, seeding scripts, deploy, test scenarios, docs | T+4h: audit + seed script |

**Members 1 and 7 both work on frontend.** Nine UI surfaces in 48 hours is not a one-person job, and
frontend is what the judges actually see. This is the highest-leverage staffing decision in the plan.

---

## Timeline

### Block A — T+0 to T+8 (foundation)
| Owner | Task |
|---|---|
| 1 | `git init`, branch structure, `.env.example`, README, both apps booting, CI running lint + tests |
| 2 | Catalog generator: 500 trekking SKUs across 3 sources, ₹ prices, ~30% cross-listed, offers |
| 3 | `SemanticIndex` (TF-IDF), `ranking.py` with the §18 weighted scorer + `ranking.yaml` |
| 4 | `vocabulary.py`, condition DSL + tests, `trek.yaml` and `winter_trek.yaml` |
| 5 | `LLMProvider` + Gemini client, `understand()` with strict JSON schema **and its regex fallback** |
| 6 | FastAPI skeleton, all ORM models, Alembic-free `create_all`, repositories, `/api/health`, product search |
| 7 | Vite+TS+Tailwind+shadcn, design tokens, landing page, chat shell against mocks |
| 8 | `seed.py`, audit logger, mock fixtures for every contract endpoint, `.github/workflows/ci.yml` |

**T+8 GATE:** `/api/products/search` returns real trekking products. Landing + chat render. If the
catalog is not queryable at T+8, everything downstream slips — Member 1 reassigns help to Member 2.

### Block B — T+8 to T+20 (the spine)
| Owner | Task |
|---|---|
| 1 | Frontend: requirements page, product cards, comparison table |
| 2 | Catalog to ~2,000 SKUs (home + electronics), `validate_vocab.py`, `validate_coverage.py` |
| 3 | Full scorer wired to search; `goal_suitability` via tag/feature overlap; badge assignment |
| 4 | `requirement_planner.py`: KB → requirements, quantity rules, existing-item fuzzy matching |
| 5 | Orchestrator FSM, slot policy, `ask()`, question cap, session persistence |
| 6 | `/api/chat`, `/api/session`, `/api/requirements/*`, `/api/recommendations` |
| 7 | Chat page complete: message stream, sidebar (collected/missing/assumptions), chips, progress |
| 8 | Guardrails: privacy scrub, budget assertion, grounding check. Scenario tests 1–4. |

**T+20 GATE — the make-or-break checkpoint.** Chat → slots → requirements → products works end to
end. If it does not, we cut the admin dashboard, profile page, and CF *immediately* and everyone
converges on the spine. **Do not defer this decision to T+30.**

### Block C — T+20 to T+32 (the payoff)
| Owner | Task |
|---|---|
| 1 | Integration, bug triage, frontend: bundle page |
| 2 | Catalog to 3,000, synthetic interactions (~15k), public dataset ingest |
| 3 | CF over interactions, hybrid blend, Precision@K / Recall@K / NDCG@K vs popularity baseline |
| 4 | **Bundle optimizer** (feasibility → greedy → add-ons → local search) + substitution engine |
| 5 | `explain()` grounded in score breakdown, refinement turns ("why this?", "something cheaper") |
| 6 | `/api/bundle/optimize`, `/api/shopping-plan/{id}`, `/api/explain`, `/api/compare`, `/api/substitute` |
| 7 | Discovery + comparison pages complete, explanation modal with the scorecard |
| 8 | Deploy: Neon + Render + Vercel with env vars. Scenario tests 5–8. |

**T+32 GATE:** full journey works on the deployed URLs, not just localhost.

### Block D — T+32 to T+42 (polish + hardening)
- Feedback buttons, preference tracking, profile page, admin dashboard *(first things cut if behind)*
- Empty states, loading skeletons, error cards, mobile-responsive pass
- **Chaos test (Member 8): revoke the Gemini key and run the demo.** It must still complete. This is
  the single most valuable test in the project — LLM APIs fail on stage.
- Seed a pristine demo database; snapshot it; document the one-command restore
- README, `AI_USAGE.md`, architecture diagram, ML evaluation results

### Block E — T+42 to T+48 (freeze)
- **T+42: hard code freeze.** Only demo-breaking bug fixes after this point.
- Full run of the 8 test scenarios on production URLs
- Demo script rehearsed 3× end to end, timed
- Backup plan: local instance running, plus a recorded video of a successful run

---

## Cut lines — decide by T+20, not at T+40

| Priority | Feature | Cut when |
|---|---|---|
| Never | chat, slots, requirements, search, ranking, bundle, plan | — |
| Low | Collaborative filtering | behind at T+20 → ship content-based + popularity, say so honestly |
| Low | Admin dashboard | behind at T+24 |
| Low | Profile page | behind at T+24 |
| Low | Public dataset ingest | behind at T+20 → curated catalog only, disclose in README |
| Low | Docker | always last |
| Zero | auth, price history, image/voice input | already out of scope |

---

## Rules of engagement

1. **Branch per member** off `develop`: `feature/frontend`, `feature/agent`, … PR into `develop`.
   `main` only receives tested merges from `develop`. Member 1 is the only person who merges to `main`.
2. **Merge to `develop` at least every 4 hours.** A 10-hour-old branch in a 48-hour hackathon is a
   merge conflict that costs more than the feature.
3. **Never break `develop`.** CI runs lint + tests on every PR. Red CI blocks the merge.
4. **No secrets in git.** `.env` is gitignored. Only `.env.example` is committed.
5. **Interfaces first.** Publish your module's function signature in the PR description before you
   implement it, so the person consuming it can start.
6. If you are blocked for more than 30 minutes, escalate to Member 1. Do not silently burn an hour.

---

## Demo-day insurance (Member 8 owns all of it)

- [ ] Pristine seeded DB snapshot + one-command restore
- [ ] Gemini key revoked → full journey still completes (fallback path verified)
- [ ] Local instance running in parallel with production
- [ ] Recorded video of a successful end-to-end run
- [ ] `/api/health` green on all three services, checked 10 minutes before presenting
- [ ] The exact demo sentence saved as a clickable example on the landing page — **nobody types the
      demo prompt live**

# Architecture diagrams

Mermaid source. GitHub renders these inline; no build step.

---

## 1. System overview

```mermaid
flowchart TB
    subgraph client["Browser"]
        UI["React 18 + TypeScript<br/>Vite · Tailwind v4 · shadcn/ui"]
        Q["TanStack Query<br/>server cache"]
        Z["Zustand<br/>planId · chatSessionId · enabledSources"]
        UI <--> Q
        UI <--> Z
    end

    subgraph api["FastAPI backend"]
        R["Routers<br/>/api/chat · /products · /recommendations<br/>/bundle · /compare · /explain · /admin"]
        G["Guardrails<br/>grounding · banned claims · validation"]
        ORCH["Agent orchestrator<br/>deterministic FSM"]
        KB["Requirement KB<br/>YAML goals"]
        RANK["Ranking engine<br/>8 weighted components"]
        OPT["Bundle optimizer<br/>budget allocation"]
        SEARCH["Product search<br/>SQL filter + TF-IDF"]
    end

    subgraph data["Data"]
        DB[("SQLite / Postgres<br/>products · plans · sessions")]
        IDX["In-memory TF-IDF index"]
    end

    LLM["Google Gemini<br/>language layer only"]

    Q -->|"X-Session-Id"| R
    R --> ORCH
    R --> SEARCH
    R --> RANK
    R --> OPT
    ORCH --> KB
    ORCH <-->|"JSON in / JSON out"| LLM
    ORCH --> G
    G -.->|"reject → deterministic text"| ORCH
    SEARCH --> IDX
    SEARCH --> DB
    RANK --> DB
    OPT --> DB
    ORCH --> DB

    classDef llm fill:#fde68a,stroke:#b45309,color:#000
    classDef guard fill:#fecaca,stroke:#b91c1c,color:#000
    class LLM llm
    class G guard
```

**The load-bearing detail:** Gemini touches only the orchestrator, and only to convert
language. `RANK`, `OPT` and `SEARCH` have no LLM dependency — every number the user sees
comes from those three boxes.

---

## 2. Mode B: goal to shopping plan

```mermaid
sequenceDiagram
    actor U as User
    participant UI as React
    participant API as FastAPI
    participant AG as Orchestrator (FSM)
    participant G as Gemini
    participant KB as Knowledge base
    participant RK as Ranker
    participant OP as Optimizer

    U->>UI: "4-day winter trek in Manali,<br/>Rs 15,000, I have shoes"
    UI->>API: POST /api/chat
    API->>AG: handle_message
    AG->>G: understand (intent + slots)
    G-->>AG: {activity, budget, duration, owned}
    Note over AG,G: on failure: regex NLU,<br/>response marked degraded

    alt slots missing
        AG->>G: phrase follow-up question
        G-->>AG: question + chips
        AG-->>U: "Are you camping overnight?"
        U->>AG: "Camping overnight"
    end

    AG->>KB: resolve goal → requirement list
    KB-->>AG: 27 items, conditions evaluated
    AG->>AG: subtract already-owned
    AG->>RK: rank candidates per requirement
    RK-->>AG: scored products + breakdowns
    AG->>OP: optimize to Rs 15,000
    OP-->>AG: best_overall · best_budget · premium
    AG-->>UI: plan_id, next_action=view_requirements
    UI->>API: GET /api/requirements/{plan_id}
    UI-->>U: costed, explainable plan
```

---

## 3. Retrieval and ranking pipeline

Two stages doing two different jobs — see [EVALUATION.md](../EVALUATION.md) for the
measurements that justify the split.

```mermaid
flowchart LR
    REQ["Requirement<br/>subcategory · required features<br/>price band · search terms"]

    subgraph retrieval["Stage 1 — retrieval"]
        F1["SQL filter<br/>subcategory + min rating<br/>+ enabled marketplaces"]
        F2["Category fallback<br/>if under 6 hits"]
        F3["TF-IDF cosine<br/>on search terms"]
        F4["Price ceiling<br/>est_max x 1.35"]
    end

    subgraph ranking["Stage 2 — ranking"]
        S["Weighted score<br/>8 components"]
    end

    OUT["Top N + score breakdown"]

    REQ --> F1 --> F2 --> F3 --> F4 --> S --> OUT

    S -.- W["goal_suitability 0.25<br/>preference_match 0.20<br/>quality 0.15<br/>feature_match 0.15<br/>budget_fit 0.10<br/>review_strength 0.05<br/>delivery 0.05<br/>deal_value 0.05"]
```

Measured on 82 knowledge-base items: TF-IDF finds the right shelf (P@1 0.963) far better
than the weighted scorer does (0.780), which is exactly why the filter runs first. Within
the correct shelf the scorer leads every baseline (NDCG@10 0.995). Both figures carry
caveats documented in [EVALUATION.md](../EVALUATION.md).

---

## 4. Degradation paths

```mermaid
flowchart TD
    START["Chat turn"] --> CHK{"Gemini<br/>reachable?"}
    CHK -->|yes| L1["LLM slot extraction"]
    CHK -->|"no / timeout / 429"| F1["Regex NLU<br/>agent/fallback.py"]

    L1 --> GRD{"Guardrail<br/>passes?"}
    GRD -->|yes| OUT1["LLM prose"]
    GRD -->|"ungrounded number<br/>or banned claim"| F2["Deterministic<br/>reason strings"]

    F1 --> DEG["degraded: true"]
    F2 --> OUT2["Plan still complete"]
    OUT1 --> OUT2
    DEG --> OUT2

    OUT2 --> UI["UI shows banner<br/>when degraded"]

    classDef fallback fill:#dbeafe,stroke:#1d4ed8,color:#000
    class F1,F2 fallback
```

The journey always completes. `tests/backend/test_chaos.py` asserts this against a
provider that fails on every call: no 5xx, budget still extracted, `degraded: true` set.

---

## 5. Deployment

```mermaid
flowchart LR
    subgraph vercel["Vercel"]
        FE["Static React build<br/>frontend/dist"]
    end
    subgraph render["Render"]
        BE["uvicorn app.main:app<br/>Docker or native"]
    end
    subgraph neon["Neon"]
        PG[("PostgreSQL")]
    end
    G["Gemini API"]

    U["User"] --> FE
    FE -->|"VITE_API_BASE_URL"| BE
    BE -->|"DATABASE_URL"| PG
    BE -->|"GEMINI_API_KEY"| G
```

Locally the same topology runs as Vite dev server → uvicorn → SQLite. The only
difference is `DATABASE_URL`. See [DEPLOYMENT.md](../DEPLOYMENT.md).

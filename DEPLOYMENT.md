# Deployment

Three targets: **Vercel** (frontend), **Render** (backend), **Neon** (Postgres).
All three have free tiers sufficient for a demo.

Local equivalents: Vite dev server → uvicorn → SQLite. The only difference between
local and production is `DATABASE_URL`.

---

## Secrets

**No credential belongs in this repository.** `.gitignore` excludes `.env`,
`backend/.env` and `frontend/.env.local`; `.env.example` documents the variable names
with empty values.

| Variable | Where | Notes |
|---|---|---|
| `GEMINI_API_KEY` | Render dashboard | Without it the app runs fully on the deterministic path with `degraded: true` |
| `DATABASE_URL` | Render dashboard | Neon string, **must** use the `postgresql+psycopg://` driver prefix |
| `SECRET_KEY` | Render (`generateValue`) | Never reuse the dev default |
| `ADMIN_TOKEN` | Render (`generateValue`) | Guards `/api/admin/*` |
| `CORS_ORIGINS` | Render dashboard | The deployed frontend origin, comma-separated |
| `VITE_API_BASE_URL` | Vercel project settings | Build-time; see the Vite note below |

`render.yaml` marks every secret `sync: false`, so Render prompts for the value and it
is never written to the repo.

---

## 1. Database — Neon

1. Create a project at [neon.tech](https://neon.tech); copy the connection string.
2. Rewrite the scheme for SQLAlchemy 2 + psycopg 3:

   ```
   postgresql://user:pass@host/db?sslmode=require
   → postgresql+psycopg://user:pass@host/db?sslmode=require
   ```

   Plain `postgresql://` makes SQLAlchemy reach for psycopg2, which is not installed.
   This is the single most common first-deploy failure.

3. No migration step. `init_db()` creates the schema on first boot, and the container
   entrypoint runs `python -m scripts.seed --if-empty`, which populates the catalog once
   and no-ops on every subsequent restart.

## 2. Backend — Render

```bash
# From the repo root, with render.yaml committed:
#   New → Blueprint → point at this repository
```

Render reads `render.yaml`, builds `backend/Dockerfile`, and prompts for the
`sync: false` variables. Health check is `/api/health`, which reports database and LLM
status without exposing any credential.

Verify:

```bash
curl https://<your-service>.onrender.com/api/health
```

Expect `{"status":"ok","db":"ok","llm":"ok","catalog_size":3075}`. `llm: "unavailable"`
means the key is missing — the app still works, on the deterministic path.

> Render's free tier sleeps after inactivity. The first request after a sleep takes
> ~30s while the container wakes **and rebuilds the TF-IDF index**. Warm it before a
> demo rather than discovering this in front of judges.

## 3. Frontend — Vercel

```bash
# New Project → import the repo → set Root Directory to `frontend`
```

`frontend/vercel.json` sets the framework, build command and SPA rewrites. Set one
environment variable:

```
VITE_API_BASE_URL = https://<your-service>.onrender.com
```

**Vite inlines `VITE_*` at build time.** Changing it in the dashboard does nothing until
you redeploy — the old value is already compiled into the bundle.

The rewrite rule sends every non-asset path to `index.html`, so a refresh on
`/plan/{id}/discover` loads the app instead of 404-ing.

## 4. CORS

Set `CORS_ORIGINS` on Render to the exact Vercel origin, no trailing slash:

```
CORS_ORIGINS=https://smartbuy-ai.vercel.app
```

Locally this never bites, because the Vite dev server proxies `/api` and everything is
same-origin. That is deliberate — it means a CORS mistake cannot silently break the
local demo — but it also means production is the first place a wrong value shows up.

---

## Full stack in Docker (local)

Mirrors the production topology, Postgres and all:

```bash
docker compose up --build
```

Frontend on `:5173`, backend on `:8000`, Postgres on `:5432`. `GEMINI_API_KEY` is read
from your shell or a root `.env`; without it the deterministic path still gives a
complete demo.

Use this to catch anything that only breaks on Postgres. For day-to-day work the native
setup in [README.md](README.md) is faster and has hot reload.

---

## Pre-demo checklist

```bash
python -m pytest                       # 90 tests
python ml/evaluation/run_eval.py       # regenerate metrics if weights changed
cd frontend && npm run typecheck && npm run lint && npm run build
```

Then, against the deployed stack:

- [ ] `/api/health` returns `db: ok` and a non-zero `catalog_size`
- [ ] A full Mode B journey completes: goal → requirements → bundles → plan
- [ ] The marketplace toggle persists across a refresh
- [ ] `/api/admin/metrics` returns 401 without a token
- [ ] Backend warmed within the last few minutes (free tier sleeps)

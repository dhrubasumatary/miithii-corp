# MIITHII

An internal support copilot for B2B teams. A support agent pastes what the
customer sent; MIITHII drafts a reply grounded in the company's own docs,
checks it against the company's policy rules, and shows its full receipt —
action taken, policy flags, citations, tokens, measured cost. A named human
always reviews and sends. Nothing sends itself.

- **Product surface:** the dashboard (ticket queue → draft + receipt → copy
  into your helpdesk). Voice dictation built in.
- **Engine:** policy-gated FastAPI pipeline (classify → retrieve → policy →
  draft → validate), Postgres + pgvector hybrid retrieval, per-tenant RLS.

## Layout

| Path | What it is |
|---|---|
| `miithii-engine/` | FastAPI service, Alembic migrations, evals, CI-tested RLS |
| `miithii-dashboard/` | Next.js (static export) dashboard, deployed on Cloudflare Pages |
| `docs/evidence/` | Assumption ledger, PII flow map, product-gap register |
| `docs/pitch.md` | Design-partner outreach kit |
| `spike/` | De-risk pass artifacts (RLS probe, retrieval spike, benchmark results) |
| `ARCHITECTURE.md` | The ADRs — binding decisions, read before changing architecture |

## Development

```bash
# engine (Python 3.12 + uv)
cd miithii-engine
uv sync --extra dev
uv run pytest -q            # unit tests; DB-gated tests need DATABASE_URL
uv run uvicorn app.main:app --port 8000

# dashboard (Node 24 + pnpm)
cd miithii-dashboard
pnpm install
pnpm dev                    # build-time env comes from miithii-dashboard/.env.local
pnpm build                  # static export into out/
```

`miithii-dashboard/.env.local` (gitignored) must set `NEXT_PUBLIC_ENGINE_URL`,
`NEXT_PUBLIC_SUPABASE_URL`, and `NEXT_PUBLIC_SUPABASE_ANON_KEY` — they are
baked into the static export at build time. `.env.example` documents the
engine's variables.

## Deployment

- **Engine:** Render (Docker), free tier — `render.yaml` is the blueprint.
  Auto-deploy webhooks do not fire on this repo; deploys are manual:
  `render deploys create <service-id> --commit <sha> --wait`.
- **Dashboard:** `pnpm exec wrangler pages deploy out --project-name miithii-dashboard`.

CI runs ruff + pytest and a pgvector service job (migrate → provision app
role → RLS probe) on every push.

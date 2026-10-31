# MIITHII — Architecture Verdict & Production Plan

Source analysis: `supportpilot/` (github.com/subhamcrxz/supportpilot), analyzed 2026-10-30.
Goal: miithii = commercial AI support product. Python backend. This doc is the decision record.

---

## 1. What supportpilot actually is

A policy-gated support-ticket AI engine (~2,000 lines of Python in `services/ai-engine`):

```
ticket → classify (keyword rules) → PolicyEngine (deterministic, AUTHORITATIVE)
       → retrieve docs (keyword scoring) → LLM drafts answer (Gemini)
       → validator (post-generation safety) → response + action + sources
```

7 possible actions: answer, clarify, refuse, refuse_and_guide, human_review, escalate, refuse_and_escalate.
Plus: Next.js demo UI, a dead Fastify API shell, unused Postgres+Redis compose, and a genuinely
good eval harness (50 labeled CloudDesk tickets, benchmark with latency percentiles).

## 2. The cool shit (keep — this is the moat)

1. **Policy engine is authoritative, LLM is a mouthpiece.** `validator.py:53` raises if the LLM
   changes the action. This is the same pattern commercial support AI (Intercom Fin, Decagon) uses.
   Most hobby projects let the LLM decide. Don't ever lose this.
2. **Post-generation validation.** Catches workflow-hallucination ("I have escalated your request")
   and refusal-leakage. Real safety engineering; rare in small codebases.
3. **Fail-closed auth** (`auth.py`) — unconfigured API key = 503, timing-safe compare.
4. **Eval-first.** 50 labeled tickets incl. adversarial cases (prompt injection, secret extraction,
   verification bypass), resumable benchmark with P50/P95. This is the hardest part of shipping
   LLM products and it exists here as a template.
5. **Provider abstraction** — `AIProvider` ABC, deterministic zero-cost fallback, Pydantic-typed
   structured output contracts.
6. Clean modern Python 3.12: StrEnum, pydantic v2, pydantic-settings, hatchling, ruff, layered
   package layout (domain/intake/policy/retrieval/providers/pipeline/routes).

## 3. The wack shit (fix or delete)

1. **Classifier is a 300-line English keyword wall** (`classifier.py:31-295`). 23 hardcoded phrasings
   of "give me my api key". Any synonym or non-English text bypasses EVERY safety net. Weakest link
   feeds the strongest layer.
2. **Half the policy engine is unreachable in live mode.** `PolicyEngine` handles tags like
   `destructive_action`, `contractual_exception`, `ambiguous`, `no_secrets` — but the live classifier
   can only emit ~8 tags. `CLARIFY` and several review paths can never fire outside the hand-labeled
   eval set.
3. **Retrieval is token-overlap scoring** (`knowledge_base.py:100-133`) + a +100 preference bonus for
   category-mapped docs. Only works because the corpus is 17 files. pgvector is provisioned in
   docker-compose and used by ZERO code.
4. **Eval mode cheats.** `analyze()` (eval path) fetches exactly the docs the ticket *labels* as
   required — the benchmark measures generation+policy, never retrieval.
5. **No persistence anywhere.** No DB schema, no ticket store, no audit trail, no conversation
   memory. For a support product the audit trail IS the product (compliance, "why did the AI say this").
6. **Un-deployable wiring.** `routes/analyze.py:20-22` computes repo root via `parents[4]` and builds
   a module-level singleton reading markdown from the source tree on EVERY request. Depends on
   `../evals/clouddesk` existing. No lifespan, no DI.
7. **Dead layers:** `apps/api` (Fastify) = health endpoint only, yet Next.js proxies straight to the
   Python service. Redis provisioned, never referenced. `packages/prompts` is a placeholder not
   imported anywhere (real prompts live inline in `gemini.py:82-228`). `packages/types` duplicates
   pydantic models in TS.
8. **Bugs / rot:** no timeout on the Gemini call (hang = hung worker); no retry/backoff; `ProviderValidationError`
   (a server-side failure) maps to HTTP 400 in `analyze.py:68-72` — should be 502; difficulty enum has
   HARD, never assigned; benchmark print block (`test_gemini_benchmark.py:229-241`) is scrambled but
   happens to run; `.env.example` lists OPENAI_API_KEY + DB URLs nothing reads; docs claim "AI not
   implemented" while it is. 6 commits, Aug 13–16 2026, dead since — a weekend sprint, never finished.
9. **Zero multi-tenancy.** One global hardcoded fictional company (CloudDesk). Commercial = every
   customer gets their own docs, policies, and keys.
10. **No observability** — zero logging statements, no metrics, no tracing, no cost accounting.

## 4. The verdict

Keep the skeleton (pipeline + policy-authority + validator + provider abstraction + eval mindset).
Delete the dead TS layers. Rebuild the weak organs (classifier, retrieval, persistence, deployment).

### Keep
- `pipeline` shape, `PolicyEngine` pattern (generalize to per-tenant config), `validator` pattern,
  provider ABC + deterministic fallback, eval harness concept, CloudDesk dataset as a fixture.

### Delete
- `apps/api` (Fastify) — Python-only backend; Next.js calls FastAPI directly.
- `packages/types`, `packages/config`, `packages/prompts` — fold prompts into Python as versioned
  YAML/markdown files loaded at startup.
- Redis until queues/rate-limiting actually exist.
- `.env.example` stale keys, stale docs sections.

### Build (priority order)
1. **Postgres + pgvector as the real store** — SQLAlchemy 2.0 async + asyncpg + Alembic. Tables:
   `tenants, users, api_keys, knowledge_sources, chunks(embedding vector), tickets, analyses(audit),
   conversations, usage_ledger(cost/tokens per request)`. Postgres RLS for tenant isolation.
2. **Ingestion pipeline** — per-tenant doc upload (md/pdf/html/url) → chunk → embed → pgvector.
   Background jobs via arq (Redis) once real; BackgroundTasks to start.
3. **Retrieval upgrade** — hybrid: pgvector cosine + Postgres full-text (tsvector) → rerank
   (Cohere or a cross-encoder) → top-k with per-claim citations.
4. **Classifier upgrade** — LLM structured-output classification (cheap fast model) with the keyword
   list demoted to a free pre-pass; low confidence → CLARIFY/human. This unlocks the dead policy branches.
5. **Resilience** — async httpx/genai client, explicit timeouts, tenacity exponential backoff,
   circuit breaker → deterministic provider fallback, SSE streaming for the UI.
6. **Observability** — structlog JSON logs, request-id middleware, OpenTelemetry, Langfuse (or similar)
   for LLM traces, per-tenant cost tracking fed into `usage_ledger`.
7. **Product auth** — dashboard JWT (Auth.js on Next.js) + per-tenant API keys for the engine;
   per-key rate limiting.
8. **Ship path** — Dockerfile (multi-stage) for the engine → Fly.io/Railway; managed Postgres with
   pgvector (Neon/Supabase); GitHub Actions CI: ruff + pytest + eval smoke test on the golden set.

## 5. Python skills ladder (deepest → what miithii needs)

- **L1 — repo already demonstrates:** FastAPI routing, Pydantic v2 contracts, settings, pytest, ruff.
- **L2 — required for prod:** SQLAlchemy 2.0 async + asyncpg, Alembic migrations, FastAPI lifespan +
  dependency injection, httpx async, tenacity, structlog.
- **L3 — AI engineering:** embeddings + chunking strategy, pgvector / hybrid retrieval, reranking,
  structured outputs, prompt versioning, eval harnesses, SSE streaming, LLM cost/latency budgeting.
- **L4 — commercial hardening:** background queues, idempotency, per-tenant rate limiting, OTel
  tracing, OWASP-for-LLM (injection, PII redaction — presidio), Postgres RLS, load testing,
  Docker multi-stage, CI/CD.

## 6. External tooling decisions (2026-10-30)

- **justPostgres (hiteshchoudhary) — REJECTED.** It's a pre-alpha control plane for running MANY
  postgres databases from one host (no test suite, 11 commits, known isolation issue). Miithii needs
  ONE postgres with pgvector. Managed Postgres (Neon/Supabase) gives backups, PITR, pooling with zero
  code to operate. Adopting it would be pure burden. Revisit only if we ever sell per-tenant
  dedicated databases or data-residency self-hosting.
- **Supabase Compute (private alpha, 2026-10) — WATCHLIST, not now.** Free during alpha but
  waitlist-only, us-west-2 only, explicitly "evaluation only, not production; may change or end",
  no GA date/pricing, no autoscaling/persistent disk, every service receives all project secrets.
  FastAPI would run fine on it (Dockerfile runtime) but building a commercial product on a
  non-production alpha is building on sand. The DB-adjacency latency win is irrelevant for us — our
  per-request latency is dominated by LLM calls, not DB round trips. Revisit at GA for the ingestion
  worker / long-running agents; because our state already lives in Postgres and everything runs from
  a Dockerfile, adopting it later is a deployment swap, not a rearchitecture.
- **supermemory (supermemoryai) — DEFERRED, adapter-gated.** Serious project (31.5k★, MIT, Python
  SDK, hybrid search + connectors + memory). NOT in the MVP: retrieval is miithii's core moat and
  stays ours (pgvector hybrid in our own DB); adding it now means a second service + second datastore
  + sending customer PII to a third-party API. REVISIT at phase 3+ for exactly two jobs, each behind
  an adapter interface we own so we can drop it without touching the engine:
  1. ingestion connectors (Google Drive / Notion / GitHub / webhooks, multi-modal PDF/OCR/video) —
     adopted only when paying customers demand connectors;
  2. cross-ticket conversation memory ("customer already tried X last week").
  Self-hosted (Docker) only for PII contexts; hosted API only for non-sensitive content.

## 7. Phase plan (summary — full detail in session notes)

- P0 (day 1): decisions locked (this doc), new `miithii-engine/` FastAPI service, uv, CI skeleton.
- P1 (wk 1): app factory, lifespan, structlog+request-id, Alembic schema (tenants, users, api_keys,
  knowledge_sources, chunks+vector, tickets, analyses, usage_events) + RLS, CI (ruff/mypy/pytest).
- P2 (wk 2): port the brain — enums, PolicyEngine (per-tenant config rows), validator, provider ABC +
  deterministic fallback; Gemini provider async w/ timeout+backoff+cost capture; classifier v2 (LLM
  structured output, keyword pre-pass, confidence gate → clarify/human).
- P3 (wk 3): ingestion API (md/txt/pdf → chunk → embed → pgvector), hybrid retrieval (vector +
  tsvector, RRF), citations; eval harness measures retrieval honestly.
- P4 (wk 4): product surface — /v1/tickets (+persist audit), conversations, SSE streaming, hashed
  per-tenant API keys + rate limits; Next.js talks to engine directly.
- P5 (ongoing): golden set growth, eval-gate in CI, benchmark (accuracy/refusal/citations/latency/cost).
- P6 (wk 5–6): Docker multi-stage, Fly/Railway deploy, Neon prod, staging env, Sentry+Langfuse.
  Stripe only post-MVP.

## 9. First-principles reset — market-first (2026-10-30)

> **CORRECTION (2026-10-30, same day): MIITHII is an INTERNAL copilot, not a customer-facing
> widget.** The end users are the tenant company's own support employees; ticket authors never
> touch miithii directly. This supersedes the product-surface bullets below:
> - The embeddable widget is DELETED from v1 (no embed.js, no Turnstile, no CSP/Shadow-DOM work).
> - The dashboard IS the product: ticket queue → draft answer + policy action + citations →
>   employee edits & sends. Human-in-the-loop is v1's trust model.
> - Conversations/messages tables persist (as ticket threads + draft history + audit), SSE stays
>   (draft streaming in the dashboard).
> - Tickets enter pull-based in v1 (paste, email-forward); helpdesk integrations (Zendesk/
>   Freshdesk/Intercom/Slack) move to P7 alongside connector demand.
> - Pricing: per-seat B2B (per employee), not per-conversation.
> - CloudDesk is now dual-purpose: the safety harness AND the built-in sandbox demo tenant that
>   every prospect can try before ingesting their own docs.
> - "Flip the switch" (autonomous customer-facing answers) is a P7+ per-tenant, per-category
>   policy setting, unlocked only when that category's audit metrics prove it is safe. The
>   pipeline is unchanged; the human gate becomes configurable.
> - whirl (below) remains reference-only for dashboard UX.

Supersedes §7 where they differ. Goal: in-market and useful before any real spend.

**Scope clarifications:**
- CloudDesk's 50 tickets are the INTERNAL SAFETY HARNESS (eval fixture), never the product
  surface. The product operates on each tenant's OWN data.
- Product surface v1 = ① embeddable chat widget (embed.js, SSE streaming) for the tenant's
  site, ② dashboard: docs management + conversation inbox + audit trail, ③ ingestion:
  **web/sitemap crawler** (tenant gives docs/help-center URLs → we fetch, extract, chunk,
  embed — pure Python: httpx + trafilatura/sitemap) + file upload (md/txt/pdf).
- Chat threads are v1 CORE: `conversations`/`messages` tables, thread context fed to the
  pipeline, human handoff on policy escalation.
- **whirl (whirlchat/whirl) — REFERENCE ONLY, not a dependency.** MIT ChatGPT-style app on
  Convex+Clerk+OpenRouter; coupled to a stack we don't use. Borrow UX patterns (streaming
  message states, thread/folder UX, share links); our widget is a far smaller surface.

**Free-tier deployment matrix ($0 to first paying customer):**
| Concern | Choice (free) | Notes |
|---|---|---|
| Frontend/landing/widget | Cloudflare Pages | commercial OK; **Vercel Hobby is non-commercial** — avoid |
| FastAPI engine 24/7 | Koyeb free or Fly.io (~$2–3/mo) | Oracle Always-Free ARM = $0 box later if self-ops wanted |
| Postgres+pgvector+auth | Supabase free (500MB) | auth bundle saves dashboard auth; Neon free = pure-Postgres alt; engine code identical either way |
| Jobs/queue | FastAPI BackgroundTasks → Upstash Redis free + arq | only when ingestion outgrows inline |
| Object storage | Supabase storage / R2 10GB (no egress) | raw doc uploads |
| LLM | Gemini free tier (dev) → Flash paid (prod, cents/ticket) | alternates behind provider ABC: Groq/OpenRouter free |
| Errors | Sentry free (5k/mo) | releases + alerting |
| LLM traces/cost | Langfuse Cloud free | per-tenant traces, cost, eval tags |
| Metrics (optional) | Grafana Cloud free OTel | add post-launch |
| Uptime | Healthchecks.io / UptimeRobot free | ping /health |
| Bot abuse on widget | Cloudflare Turnstile free | widget + ingest endpoints |
| Email | Resend free 3k/mo | handoff notifications |
| Payments | Stripe Checkout (post-revenue); Paddle/LemonSqueezy if MoR tax handling wanted | |

**Revised phases:** P1 foundation (as §7) → P2 brain port (as §7) → P3 ingestion v1 incl.
crawler → P4 widget+threads+inbox+docs UI → P5 evals/CI gate (as §7) → P6 ship on free
matrix + 5 design partners → P7 post-revenue: Stripe, connectors (supermemory adapter
gate), cross-ticket memory, helpdesk integrations (Slack/Zendesk).

## 10. Ground rules (carried into all miithii agents)

1. The policy decision is code, never the LLM.
2. Every LLM response passes validation before it reaches a customer.
3. Every analysis is persisted (audit trail) before the response is returned.
4. Every prompt/eval change runs against the golden set before merge.
5. Fail closed on safety; degrade to deterministic fallback on LLM failure.

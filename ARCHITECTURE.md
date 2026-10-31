# MIITHII — Architecture Decision Records

Decisions as falsifiable ADRs (2026-10-31 de-risk pass). Evidence: `docs/evidence/assumption-ledger.md`
(claims with dated quotes), `spike/results/` (measured numbers), PII: `docs/evidence/pii-flow-map.md`.
Original narrative archived at `docs/archive/architecture-v1-narrative.md`.
Project conventions: `.zcode/skills/evidence-ledger/SKILL.md`. Reference repo (never deployed): `supportpilot/`.

**Status legend:** accepted (current plan) | measured (validated by a run) | proposed (default unless refuted) | superseded (see replacement).

---

**ADR-001 — Python-only backend.** FastAPI service (`miithii-engine/`); Next.js frontend calls it directly; no TypeScript API layer.
Falsified if: dual-language overhead ever pays for itself (we need a TS-only integration surface customers demand).
Status: accepted.

**ADR-002 — Postgres+pgvector is the ONLY datastore.** Supabase free for dev (verified: 500MB, 1-wk inactivity pause, 2 active projects), Neon free as fallback (verified: 1GB/project, 100 CU-hrs). Tables: tenants, users, api_keys, knowledge_sources, chunks(vector), tickets, analyses, conversations, usage_events. No Redis until a measured queue need.
Falsified if: vector recall/latency on live pgvector fails the P1 rerun of the spike (ledger #20), or 500MB blocks the first design partner before Pro upgrade ($25, trivial).
Status: accepted (isolation pattern: measured — ADR-003).

**ADR-003 — Multi-tenancy = shared schema + tenant_id + RLS session-var policy.** `SET app.current_tenant` + `USING (tenant = current_setting(...))` + FORCE RLS; one non-superuser app role.
Falsified if: the CI probe (port of `spike/rls_probe.py`, which **PASSED on Postgres 18.6**: isolation holds, fail-closed on unset, cross-tenant UPDATE = 0 rows) ever fails, or RLS overhead on top-10 queries is material (ledger #22 test task).
Status: measured.

**ADR-004 — The policy decision is deterministic code; the LLM is a mouthpiece.** PolicyEngine emits the action (7-action taxonomy); the LLM drafts within it; validator rejects override attempts and workflow-hallucination claims.
Falsified if: tenant policies prove too diverse for config rows (policy-as-data fails) — then policy DSL v2, never LLM-discretion.
Status: accepted (pattern ported from supportpilot; its SDK-rotted error mapping is NOT ported — ADR-006).

**ADR-005 — Every analysis is persisted (tickets + analyses audit trail) BEFORE the response is returned.** This is the sales asset ("why did the AI say that") and the future autonomy evidence base.
Falsified if: audit write adds >100ms p95 to the critical path (measure, then batch-write if so — never drop).
Status: accepted.

**ADR-006 — Provider ABC + deterministic fallback; first provider Gemini on PAID tier for anything tenant-related.** Free tier only for dev with synthetic data (ledger #11: free tier trains on content — B2B blocker). Async client, explicit timeouts, tenacity backoff, error taxonomy rebuilt for google-genai 2.34 (supportpilot's `errors.RateLimitError` mapping is dead code — verified empirically, ledger #15). OpenRouter behind the same ABC as alternate (verified free limits 20 RPM / 50–1000 RPD; data-use terms unchecked → never tenant data).
Falsified if: paid-tier cost exceeds $0.01/ticket in practice (measured ~$0.001–0.002 — recheck after prompt changes) or a provider outage outlives the deterministic fallback's usefulness.
Status: accepted; free-tier 503 "high demand" observed → paid tier from first pilot.

**ADR-007 — Classifier v2: LLM structured-output classification with keyword pre-pass and confidence gate.** Low confidence routes to clarify/human_review (unlocks the policy branches that were dead code in supportpilot).
Falsified if: classification latency+cost exceeds budget (measure; fall back to hybrid keyword+embeddings classifier) or action accuracy drops on the golden set vs keyword baseline (eval-gated).
Status: proposed.

**ADR-008 — Retrieval = hybrid (vector + Postgres FTS, RRF fusion), but corpus prep is the priority.** Spike (measured, 30 queries, real docs): hybrid hit@1 63% vs vec 60% vs BM25 43%; failures dominated by extraction quality (2 pages → 46/628 chars of nav junk) and chunk granularity (162KB page). So: heading-aware chunking, extraction-quality checks at ingest (reject/nag pages below a text threshold), dedup — before any reranker.
Falsified if: live-pgvector rerun (ledger #20) diverges from spike, or a design-partner corpus shows hybrid < vec-only — then simplify (YAGNI the BM25 half).
Status: measured.

**ADR-009 — Ingestion v1: web/sitemap crawler + file upload (md/txt/pdf); connectors deferred.** Per-tenant source versioning; embed via API (Gemini embeddings — quality vs local bge is ledger #21's test task).
Falsified if: a paying tenant demands a specific connector — then adopt supermemory behind an owned adapter (its value is connectors/multi-modal, not core retrieval) rather than building the connector.
Status: accepted.

**ADR-010 — Hosting: engine on Fly.io shared-cpu-1x (~$2.19/mo, verified — no free tier for new orgs); frontend on Cloudflare Pages free (verified: no commercial restriction; static requests free/unlimited; Vercel Hobby verified non-commercial — avoid). DB Supabase free → Pro at need.**
Falsified if: Fly 256MB is insufficient for the ONNX/embedding path under load (measure at P3; then 512MB ~$4/mo, still trivial) or Cloudflare ToS adds a commercial clause (recheck terms at launch).
Status: accepted (supersedes v1's "Koyeb free" — REFUTED, ledger #7).

**ADR-011 — Observability: structlog JSON + request-ID middleware; Sentry (errors); Langfuse (LLM traces — masked per PII map); usage_events for per-tenant cost.** Grafana/OTel deferred to post-launch.
Falsified if: trace masking blocks incident debugging for a month — then per-tenant opt-in full-text tracing, never default.
Status: accepted.

**ADR-012 — Product = internal copilot (B2B per-seat). Employees are the users; ticket authors never touch miithii. Dashboard = the product: ticket queue → draft + action + citations → human edits and sends. No customer-facing widget in v1; no anonymous traffic.**
Falsified if: design partners' agents reject drafts consistently (measure acceptance rate in the dashboard from day one — it's an A/B metric we already persist via analyses).
Status: accepted (2026-10-30 correction).

**ADR-013 — CloudDesk = eval harness (50 labeled tickets, CI gate, deterministic mode, zero network) AND the built-in sandbox demo tenant.** Golden set grows from every real incident/prompt change; benchmark must measure retrieval with RETRIEVED docs, never the labels' required_sources (supportpilot's benchmark cheats there).
Falsified if: the demo tenant diverges from real ingest paths (then it's a lie — keep demo on the production pipeline).
Status: accepted.

**ADR-014 — Autonomy ("flip the switch") is a per-tenant, per-category flag unlocked by audit evidence.** The pipeline is unchanged; the human gate becomes configurable only where a category's accept-unedited rate proves safety.
Falsified if: any category reaches autonomy without a measured accept-rate threshold in usage_events.
Status: proposed (P7).

---

## Pre-mortem (miithii is dead in 3 months — why?)

1. **Retrieval fails on real tenant data** (messy Confluence/PDF, not clean docs sites). Spike already showed extraction+chunking dominate errors → caught by: ADR-008 ingest quality gates + ledger #20/#21 tests + P3 eval on the design partner's real corpus.
2. **Free-tier LLM flakiness torpedoes the pilot UX.** Observed 503 "high demand" on first live call → caught by: ADR-006 paid tier from pilot ($0.001–0.002/ticket is noise), deterministic fallback, rebuilt error taxonomy.
3. **Nobody to sell to** — built for an imaginary user. Caught by: the human gate — 3 real support agents score 10 real drafts (accept/edit/reject) BEFORE dashboard polish; acceptance rate is a persisted metric from day one (ADR-012).
4. **Supabase free pause/limits bite mid-pilot.** Verified: 1-week inactivity pause, 500MB. Caught by: keep-alive + upgrade trigger metric in usage_events; Pro is $25 and code-identical (ADR-002).
5. **Scope creep kills the solo builder** (widget, memory, connectors, integrations). Caught by: this ADR set's explicit defer/supersede statuses, the evidence-ledger skill's "no silent scope" rule, and depth-not-breadth acceptance criteria on every build task.

## Phase plan (unchanged shape, evidence-updated)

P0/P1 scaffold + schema + RLS probe in CI → P2 brain transplant (fixed error taxonomy, paid-tier provider) → P3 ingestion + retrieval (ingest quality gates per ADR-008) → P4 dashboard product + evals gate → P5 Fly/Cloudflare/Supabase ship + 5 design partners → P6+ per pre-mortem guardrails. Accounts still needed from the user: Gemini (have key), GitHub remote, Supabase project.

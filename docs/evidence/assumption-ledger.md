# MIITHII Assumption Ledger (2026-10-31)

Convention per `.zcode/skills/evidence-ledger/SKILL.md`: every load-bearing claim is
VERIFIED (dated primary-source quote), MEASURED (produced by a run in this workspace),
REFUTED (dated counter-evidence), or UNKNOWN (with a test task).

## Deployment & hosting

| # | Claim | Verdict | Evidence |
|---|---|---|---|
| 1 | Vercel Hobby is non-commercial | **VERIFIED** | vercel.com/pricing (2026-10-31): "Our Hobby plan is for personal, non-commercial use." Pro = $20/mo |
| 2 | Cloudflare free allows commercial use | **VERIFIED** (no restriction found) | developers.cloudflare.com/workers/platform/pricing (2026-10-31): Workers Free "100,000 per day" requests, 10ms CPU, "Requests to static assets are free and unlimited", paid "$5 USD per month" minimum, no egress charges. No non-commercial restriction stated on the official pricing page; staff/community confirmations (community.cloudflare.com). Explicit ToS clause not quoted → recheck cloudflare.com/terms before launch |
| 3 | Supabase free = 500MB DB, pause, auth+storage | **VERIFIED** (with correction) | supabase.com/pricing (2026-10-31): "500 MB database size", "Free projects are paused after 1 week of inactivity", 2 active projects, 50,000 MAU auth, 1 GB file storage, 5 GB egress, Pro from $25/mo |
| 4 | pgvector available on Supabase (incl. free) | **VERIFIED** | supabase.com/docs/guides/database/extensions/pgvector (2026-10-31): supported extension, enabled via dashboard/SQL; no plan restriction stated |
| 5 | Neon free as alternative | **VERIFIED** (better than planned) | neon.com/pricing (2026-10-31): 1 GB/project (plan said 0.5), 20 GB account total, 100 CU-hrs/project/mo, autosuspend "After 5 min", 100 projects, Launch = usage-based no minimum |
| 6 | Fly.io: no free tier, ~$2-3/mo smallest VM | **VERIFIED** | docs.fly.io/about/pricing (2026-10-31): "New organizations don't have a free tier or a monthly free usage allowance." shared-cpu-1x 256MB = "$2.19/month"; Managed Postgres = $38/mo (confirms using Supabase/Neon for DB) |
| 7 | Koyeb free web service tier | **REFUTED** | koyeb.com/pricing (2026-10-31): no free web service listed; entry plan Pro "$29/mo +compute"; only "Free 5h" Postgres demo + startup credits. → Engine hosting decision changed to Fly.io (see ADR-010) |
| 7b | Cloud Run as Fly alternative (free tier) | **VERIFIED** | cloud.google.com/run/pricing (2026-10-31): 2M requests/mo free, 180k vCPU-s + 360k GiB-s (request-based billing), scale-to-zero default with idle unbilled, no commercial restriction stated. Requires GCP billing account (card). Deploys the validated miithii-engine image directly |
| 7c | Render free web service | **VERIFIED (weaker)** | render.com/pricing (2026-10-31): "Free ... $0/month 512 MB RAM free", hobby bandwidth "5 GB included per month"; free plans "designed to help you to explore new tech, build personal projects" (commercial gray zone); spin-down documented on /docs/free not the pricing page |
| 7d | DigitalOcean as engine host (no Google) | **VERIFIED** | digitalocean.com/pricing (2026-10-31): Container Registry Starter "$0/month" (1 repo, 500 MiB — fits slim image); App Platform cheapest container instance "$5.00/mo" (1 vCPU, 512 MiB, always-on, no free dynamic tier); alternative $4 Droplet running validated compose. Total ~$4-5/mo |
| 8 | Langfuse free tier limits | **UNKNOWN** | pricing page fetch throttled (2026-10-31). TEST TASK: check langfuse.com/pricing at P6; pick per-tenant trace budget |
| 9 | Sentry free 5k errors/mo, Upstash 10k cmd/day | **UNKNOWN** | not fetched. TEST TASK: verify at P6 before wiring |

## LLM provider (Gemini)

| # | Claim | Verdict | Evidence |
|---|---|---|---|
| 10 | Gemini flash free tier exists | **VERIFIED** | ai.google.dev/gemini-api/docs/pricing (2026-10-31): all listed flash models "Free tier: free of charge" |
| 11 | **Free tier trains on your content; paid does not** | **VERIFIED** — THE B2B fact | same page: free tier "Content used to improve our products" = Yes; paid tier = No. → Production tenant data requires PAID tier (see ADR-006, PII map) |
| 12 | Flash paid prices | **VERIFIED** | same page: Flash 3.8/3.6 = "$0.75 through December 31, 2026. $1.50 starting January 1, 2027" in / "$3.75" out ($7.50 in 2027); 3.5 Flash-Lite = "$0.30" in / "$2.50" out per 1M |
| 13 | Concrete free-tier RPM/RPD numbers | **UNKNOWN** (by design) | rate-limits page publishes no concrete figures: "Specified rate limits are not guaranteed", limits per project, reset midnight Pacific, "429 RESOURCE_EXHAUSTED" on exceed; per-model limits visible only in AI Studio |
| 14 | Free tier reliable enough for pilots | **REFUTED as-is** | Empirical (2026-10-31, real call with project key): `503 "gemini-3.1-flash-lite is currently experiencing high demand"` on first benchmark attempt. Free tier is demand-throttled → pilots on paid tier ($0.001-0.002/ticket) or accept flakiness |
| 15 | SupportPilot provider error mapping works on current SDK | **REFUTED** | Empirical: google-genai 2.34.0 (installed 2026-10-31) has no `errors.RateLimitError` — `gemini.py:42` raises AttributeError, masking real 429/503. The repo's error taxonomy is dead code vs today's SDK → rebuild error handling in miithii-engine (ADR-006) |

## Architecture claims

| # | Claim | Verdict | Evidence |
|---|---|---|---|
| 16 | Hybrid retrieval (vec+BM25/RRF) beats naive embeddings | **MEASURED — marginal win** | spike/results/spike_results.json (2026-10-31, 30 queries, 20 real docs pages, local bge-small): hybrid hit@1 63% vs vec-only 60% vs BM25 43%; hit@3 80/77/80. Gain is real but small; failure analysis shows corpus extraction + chunk granularity dominate errors (2 pages extracted 46/628 chars; 162KB page chunked too coarse). SEE ADR-008 |
| 17 | RLS session-variable tenant isolation is safe | **MEASURED — PASSED** | spike/rls_probe.py on Postgres 18.6 (2026-10-31): tenant A/B isolation, fail-closed on unset tenant, cross-tenant UPDATE touches 0 rows, FORCE RLS on |
| 18 | SupportPilot deterministic harness works | **MEASURED — with caveats** | spike/results/deterministic_benchmark.json (2026-10-31): 50/50 action accuracy, 100% escalation accuracy, P50 4.66ms. Caveats: eval path uses LABELED required_sources (measures plumbing, not retrieval); suite cannot even collect without GEMINI_API_KEY set (import-time provider instantiation) |
| 19 | Per-ticket LLM cost | **MEASURED** | ~974 fixed prompt tokens + ticket; realistic ticket ≈ 1,350–1,420 tokens total (cl100k approximation) → **~$0.0012/ticket** on Flash-Lite paid ($0.30/$2.50), ~$0.002 on Flash |
| 20 | pgvector parity with spike's numpy cosine | **UNKNOWN** | TEST TASK (P1): rerun spike queries against live pgvector on Supabase dev project; compare hit-rate + query latency |
| 21 | Gemini embedding API quality vs local bge-small | **UNKNOWN** | TEST TASK (P2): embed same corpus+queries via Gemini embeddings API with project key; compare hit-rate |
| 22 | RLS performance overhead at scale | **UNKNOWN** | probe proves correctness, not perf. TEST TASK (P4): EXPLAIN ANALYZE top-10 product queries with RLS on vs off |

## OpenRouter (alternate provider behind ADR-006 ABC)

| # | Claim | Verdict | Evidence |
|---|---|---|---|
| 23 | Free model limits 20 RPM, 50/day (1000/day ≥10 credits) | **VERIFIED** | openrouter.ai/docs/api/reference/limits (2026-10-31): ":free" models 20 req/min; 50 req/day "< 10" credits, 1000/day "At least 10" credits. Data-use terms NOT on this page → check separately before sending any tenant data |

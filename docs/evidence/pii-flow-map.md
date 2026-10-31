# MIITHII PII Flow Map (2026-10-31)

Where tenant ticket/doc text physically exists, and the redaction decision per location.
Governing fact (ledger #11): **Gemini free tier = "Content used to improve our products";
paid tier = not used.** Tenant PII therefore never rides the free tier.

| Location | What's there | Redaction decision |
|---|---|---|
| Postgres (Supabase) | tickets, analyses, docs, chunks — full text, the system of record | Encrypted at rest by platform. Retention: per-tenant setting; deletion on tenant offboarding (DELETE cascades + backup expiry note in ADR-002). No decision needed beyond retention policy |
| Engine logs (structlog) | request IDs, tenant IDs, action, latency, errors | **Ticket/doc TEXT NEVER logged** — log IDs and lengths only. Enforced by a structlog processor that drops known text fields (enforced in code review + test) |
| Gemini prompt (paid tier) | full ticket text + retrieved chunks | REQUIRED: paid billing on the tenant's project/our account. No free-tier calls with tenant content, ever. Record tier per request in usage_events so violations are queryable |
| Gemini prompt (free tier) | dev/testing only with synthetic data | Synthetic/CloudDesk fixture data only. CI asserts no real-tenant flag can route to free tier |
| Sentry | stack traces, request bodies (default!) | `before_send` scrubber: strip message bodies, keep IDs/exceptions. Verify scrubber with a deliberate PII test event at P6 |
| Langfuse traces | prompts + completions by default | Decision: send **prompt skeleton + token counts + costs**, redact document/ticket text via mask function; if full-text tracing is ever needed for debugging, per-tenant opt-in flag only. Ledger #8: confirm free-tier limits before relying on it |
| Backups (Supabase PITR) | full DB dump incl. text | Accepted — same trust boundary as DB; document backup retention in onboarding/security page for tenants |
| Embeddings (pgvector) | vectors, not plaintext | Accepted — vectors are not directly invertible but leak paraphrase similarity; treat as text-equivalent for access control (tenant_id + RLS on chunks table) |
| Future: email/Slack intake (P7) | forwarded threads with third parties' text | Deferred: PII review + tenant DPA checklist required BEFORE the first intake connector ships |

## B2B sales answers (from this map + ledger)
1. "Do you train on our data?" — No; and our LLM provider (paid tier) contractually does not either. Free tier is dev-only, enforced by a queryable tier log.
2. "Who can read tickets?" — RLS-enforced tenant isolation (probe-passed, re-run in CI) + humans only via your own dashboard accounts.
3. "Where does data live?" — Single Postgres (region chosen at provisioning); no third-party processing beyond the LLM provider on paid, no-training tier.

# MIITHII Product Gap Register

First-principles audit of the LIVE artifact (2026-10-31). Ground truth: SQL
counts from the production DB + a cleared-storage browser walkthrough of
https://miithii-dashboard.pages.dev. Everything here is measured, not remembered.

## Ground truth (SQL, 2026-10-31)

| table | rows | note |
|---|---|---|
| tenants | 3 | clouddesk-demo + 2 API-test leftovers (junk) |
| users | **0** | no human has ever existed in miithii |
| api_keys | 3 | all minted by builder scripts |
| knowledge_sources / chunks | 20 / 21 | 100% CloudDesk fiction, ingested by builder |
| tickets / analyses / usage_events | 16 / 16 / 16 | real session history |

Engine: 10 endpoints (health, tickets CRUD+stream, usage, knowledge×3).
Dashboard: 3 pages (tickets, knowledge, usage) + key gate.

## Definition check

> **MIITHII is an internal support copilot that drafts policy-checked,
> citation-carrying replies from a company's own docs, for support teams
> who want a human to stay the sender.**

Every existing route serves this definition. Delete list: **empty** — the
scope held through the sprint. The problem is not what we built. It is who
can reach it.

## The headline finding

**A stranger's entire affordance set on the live product is one disabled
text field** (screenshot, 2026-10-31). No signup, no key request, no contact,
no explanation of what this is. The cold journey — stranger → own tenant →
own key → own docs → cited draft — **cannot be completed without the builder
running admin scripts** (`scripts/seed_demo.py` + manual SQL). Steps 1–2 of
the product's own core journey are builder-only. miithii today is a
**single-seat demo with real product organs**, not a self-serve product.

## Gaps

### BLOCKS-REVENUE
| # | Gap | Effort | Note |
|---|---|---|---|
| 1 | **Tenant self-provisioning**: signup → tenant + key minted automatically (email verification can lag) | M | `POST /v1/signup` + provisioning service; the admin scripts already contain the logic |
| 2 | **Human identity**: `users` table empty; dashboard auth = shared tenant key in localStorage. Per-seat sales need named users (Supabase Auth + user→tenant mapping) | M | engine already verifies keys; add JWT path |
| 3 | **Buyer-facing surface**: nothing on the public URLs explains what this is, pricing, or contact. A buyer visiting pages.dev sees a key wall | S | one landing page + /contact |
| 4 | **Design partner pipeline** (human): zero prospects contacted | — | pre-mortem #1; the only item that is not code |

### HURTS-TRIAL
| # | Gap | Effort |
|---|---|---|
| 5 | Cold start ~50s after 15-min idle (Render free). Keep-warm workflow committed — verify the Actions cron has actually run | S |
| 6 | Only fictional docs ingested; no first-party onboarding content inside the product ("add your first doc" exists, but no guidance on WHAT to add) | S |
| 7 | Streaming UI lacks failure-retry (stream error surfaces a toast, composer stays empty) | S |

### POLISH
| # | Gap | Effort |
|---|---|---|
| 8 | Purge 2 api-test-* tenant junk rows + seed script spam | XS |
| 9 | Custom domain + CORS retighten after domain lands | S |
| 10 | SSE auto-reconnect on mid-stream drop | S |

## Verdict (2026-10-31)

We ended up building a **working pilot core for exactly one tenant that the
builder hand-provisioned**: real policy-gated brain (95% honest retrieval,
refusals verified on live traffic), real multi-tenant isolation (RLS probe
passed), real cost ledger, real dashboard — wrapped in a wall that stops
everyone else from existing. The next unit of work is not more engine. It is
**door #1: let a stranger in** (gap #1), then gap #2, then the partner from
gap #4 walks through it.

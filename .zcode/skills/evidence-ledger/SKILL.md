---
name: evidence-ledger
description: MIITHII project convention for verifying load-bearing claims with dated primary sources and recording decisions as falsifiable ADRs. Use whenever a plan claim, vendor limit, or pricing fact is about to be relied on or written into ARCHITECTURE.md/ADRs.
---

Every load-bearing claim in miithii docs must be one of:

1. **VERIFIED** — carries a ledger entry: `{source URL, access date, exact quote (<125 chars), verdict}` in `docs/evidence/assumption-ledger.md`. Quotes must be copied verbatim from the vendor's page, never paraphrased into the claim.
2. **UNKNOWN** — carries a test task: how we will measure it, where the test lives, what result settles it.

Rules:
- Primary sources only (vendor's own page, repo README, official docs). Blog posts about the vendor are not evidence; the vendor's page is.
- Record the access date on every entry — free tiers change quarterly; an unverified claim from memory is treated as UNKNOWN, not as fact.
- Free-tier limits and data-processing terms MUST be re-verified before any paid migration or enterprise sale conversation.
- Decisions live as numbered ADRs with a `we were wrong if…` falsification line and a status (proposed/accepted/superseded). When evidence refutes a decision, update its status to superseded and write the replacement — never silently edit history.
- New evidence lands in `docs/evidence/`; never inline in chat-only conclusions.

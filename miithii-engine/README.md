# MIITHII Engine

Internal support copilot engine — policy-gated AI pipeline (FastAPI, Python 3.12).
Architecture decisions: [`../ARCHITECTURE.md`](../ARCHITECTURE.md) (ADRs). Evidence: [`../docs/evidence/`](../docs/evidence).

## Setup

```bash
uv sync --extra dev          # creates .venv (main + dev deps)
cp ../.env.example ../.env   # then fill in DATABASE_URL / keys
```

## Run

```bash
uv run uvicorn app.main:app --reload --port 8000
```

Health: `curl http://localhost:8000/health` — reports `database: ok` when
`DATABASE_URL` is configured (session pooler, not transaction pooler — ADR-003).

## Test / lint

```bash
uv run pytest -q       # deterministic unit tests, no network
uv run ruff check .
```

## Ground rules (binding — ADRs 004–006)

1. The policy decision is deterministic code, never the LLM.
2. Every LLM response passes validation before it reaches a user.
3. Every analysis is persisted before the response is returned.
4. Ticket/doc text is never logged (see `../docs/evidence/pii-flow-map.md`).

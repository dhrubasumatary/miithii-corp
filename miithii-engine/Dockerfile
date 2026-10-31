# MIITHII Engine — production container (P5 deploy artifact).
# Multi-stage uv pattern: deps cached by layer, slim runtime, non-root user.
# NOTE: not yet exercised locally (no Docker on this machine) — validated at P5 deploy.
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder
WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./
RUN uv sync --frozen --no-dev

FROM python:3.12-slim-bookworm
WORKDIR /app
RUN groupadd -r miithii && useradd -r -g miithii miithii

COPY --from=builder /app /app
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1

USER miithii
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

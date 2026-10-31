"""Health endpoint — uptime probes (Healthchecks) and deploy smoke tests."""

from fastapi import APIRouter, Request
from sqlalchemy import text

from app.config import get_settings

router = APIRouter(tags=["health"])


@router.get("/health")
async def health(request: Request) -> dict[str, str]:
    settings = get_settings()
    payload: dict[str, str] = {
        "status": "ok",
        "service": "miithii-engine",
        "version": settings.service_version,
    }

    engine = getattr(request.app.state, "engine", None)
    if engine is None:
        payload["database"] = "not-configured"
        return payload

    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        payload["database"] = "ok"
    except Exception:  # noqa: BLE001 - health must report, not raise
        payload["database"] = "error"
        payload["status"] = "degraded"
    return payload

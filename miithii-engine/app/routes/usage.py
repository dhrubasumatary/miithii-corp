"""GET /v1/usage — per-tenant consumption and cost aggregates (14 days)."""

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import Tenant, UsageEvent
from app.security import require_tenant

router = APIRouter(prefix="/v1/usage", tags=["usage"])


@router.get("")
async def usage(
    tenant: Tenant = Depends(require_tenant),
    session: AsyncSession = Depends(get_session),
) -> dict:
    day = func.date(UsageEvent.created_at).label("day")
    rows = (
        await session.execute(
            select(
                day,
                func.count().label("events"),
                func.coalesce(func.sum(UsageEvent.prompt_tokens), 0).label("prompt_tokens"),
                func.coalesce(func.sum(UsageEvent.completion_tokens), 0).label("completion_tokens"),
                func.coalesce(func.sum(UsageEvent.cost_usd), 0).label("cost_usd"),
            )
            .where(
                UsageEvent.tenant_id == tenant.id,
                UsageEvent.created_at >= func.now() - func.interval("14 days"),
            )
            .group_by(day)
            .order_by(day.desc())
        )
    ).all()

    days = [
        {
            "day": str(row.day),
            "events": row.events,
            "prompt_tokens": int(row.prompt_tokens),
            "completion_tokens": int(row.completion_tokens),
            "cost_usd": float(row.cost_usd),
        }
        for row in rows
    ]
    totals = {
        "events": sum(d["events"] for d in days),
        "prompt_tokens": sum(d["prompt_tokens"] for d in days),
        "completion_tokens": sum(d["completion_tokens"] for d in days),
        "cost_usd": round(sum(d["cost_usd"] for d in days), 6),
    }
    return {"days": days, "totals": totals}

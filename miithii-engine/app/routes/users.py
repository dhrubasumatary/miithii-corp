"""GET/POST /v1/users — named seats (gap #2).

Free plan caps a workspace at 3 named users. Invited emails create pending
rows; their first magic-link login matches by email and goes live.
"""

import re

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import Tenant, User, UserRole
from app.security import require_tenant

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/v1/users", tags=["users"])

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_FREE_SEAT_LIMIT = 3


async def _seat_guard(tenant: Tenant, session: AsyncSession) -> None:
    if tenant.plan.value == "free":
        count = (
            await session.execute(
                select(func.count()).select_from(User).where(User.tenant_id == tenant.id)
            )
        ).scalar_one()
        if count >= _FREE_SEAT_LIMIT:
            raise HTTPException(
                status_code=402,
                detail="Free plan includes 3 named users — upgrade for more seats",
            )


class InvitePayload(BaseModel):
    email: str = Field(min_length=5, max_length=320)
    name: str | None = Field(default=None, max_length=200)


@router.get("")
async def list_users(
    tenant: Tenant = Depends(require_tenant),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    rows = (
        await session.execute(
            select(User).where(User.tenant_id == tenant.id).order_by(User.created_at)
        )
    ).scalars().all()
    return [
        {
            "id": str(u.id),
            "email": u.email,
            "name": u.name,
            "role": u.role.value,
            "joined": u.created_at.isoformat(),
        }
        for u in rows
    ]


@router.post("", status_code=201)
async def invite_user(
    payload: InvitePayload,
    tenant: Tenant = Depends(require_tenant),
    session: AsyncSession = Depends(get_session),
) -> dict:
    email = payload.email.strip().lower()
    if not _EMAIL_RE.match(email):
        raise HTTPException(status_code=400, detail="Enter a valid email address")

    await _seat_guard(tenant, session)
    existing = (
        await session.execute(
            select(User).where(User.tenant_id == tenant.id, User.email == email)
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status_code=409, detail="Already on the team")

    user = User(
        tenant_id=tenant.id,
        email=email,
        name=(payload.name or email.split("@")[0])[:200],
        role=UserRole.AGENT,
    )
    session.add(user)
    await session.commit()
    logger.info("user_invited", tenant_id=str(tenant.id), email=email)
    return {
        "id": str(user.id),
        "email": user.email,
        "name": user.name,
        "role": user.role.value,
        "note": "They sign in with this email — first login activates the seat.",
    }

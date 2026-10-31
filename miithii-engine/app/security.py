"""API-key authentication → tenant discovery → RLS binding.

Order matters: authenticate by key hash FIRST (api_keys lives outside RLS —
see migration 0002 for the chicken-and-egg rationale), then bind
app.current_tenant, THEN read the tenant row through the RLS policy.
"""

import hashlib
from datetime import UTC, datetime

import structlog
from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import bind_tenant, get_session
from app.models import ApiKey, Tenant

logger = structlog.get_logger(__name__)


async def require_tenant(
    session: AsyncSession = Depends(get_session),
    x_api_key: str | None = Header(default=None),
) -> Tenant:
    if not x_api_key:
        raise HTTPException(status_code=401, detail="Missing X-API-Key header")

    key_hash = hashlib.sha256(x_api_key.encode()).hexdigest()
    key_row = (
        await session.execute(
            select(ApiKey).where(ApiKey.key_hash == key_hash, ApiKey.revoked_at.is_(None))
        )
    ).scalar_one_or_none()
    if key_row is None:
        raise HTTPException(status_code=401, detail="Invalid API key")

    # Bind BEFORE reading the tenant row — tenants is RLS-enforced.
    await bind_tenant(session, key_row.tenant_id)
    tenant = (
        await session.execute(select(Tenant).where(Tenant.id == key_row.tenant_id))
    ).scalar_one_or_none()
    if tenant is None:
        raise HTTPException(status_code=401, detail="Invalid API key")

    key_row.last_used_at = datetime.now(UTC)
    logger.info("authenticated", tenant_id=str(tenant.id))
    return tenant

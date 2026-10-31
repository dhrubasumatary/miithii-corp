"""Authentication → tenant discovery → RLS binding.

Two principals:
1. Machines: X-API-Key (hashed lookup; api_keys sits outside RLS — migration
   0002 explains the chicken-and-egg).
2. Humans: `Authorization: Bearer <supabase-jwt>` — verified against the
   project's JWKS, mapped to a tenant by email:
     - a users row with that email wins (invited teammate),
     - else the tenant whose owner_email matches (first login = owner,
       the users row is created on the spot),
     - else 403: known human, unknown workspace.
Order matters for both paths: bind app.current_tenant BEFORE any
tenant-scoped read. Every analysis records user_id when a human acts.
"""

import hashlib
import time
from datetime import UTC, datetime

import httpx
import structlog
from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import bind_tenant, get_session
from app.models import ApiKey, Tenant, User, UserRole

logger = structlog.get_logger(__name__)

_INTROSPECTION_CACHE: dict[str, tuple[float, dict]] = {}
_INTROSPECTION_TTL = 300.0


async def _verify_supabase_session(token: str) -> dict:
    """Verify a Supabase session by introspecting it — the new sb_publishable_
    key system has no JWKS; asking the auth server is the honest check.
    Results cached briefly: the session token is the same object per login."""
    settings = get_settings()
    if not settings.supabase_url or not settings.supabase_publishable_key:
        raise HTTPException(status_code=503, detail="Human sign-in not configured")

    cached = _INTROSPECTION_CACHE.get(token)
    now = time.time()
    if cached and now - cached[0] < _INTROSPECTION_TTL:
        return cached[1]

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                f"{settings.supabase_url.rstrip('/')}/auth/v1/user",
                headers={
                    "apikey": settings.supabase_publishable_key,
                    "Authorization": f"Bearer {token}",
                },
            )
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=503, detail="Auth server unreachable") from exc

    # Supabase answers 401 OR 403 for an invalid/expired session (403 when
    # the apikey is valid but the bearer is not) — both mean "bad session".
    if response.status_code in (401, 403):
        raise HTTPException(status_code=401, detail="Session expired or invalid")
    if response.status_code != 200:
        raise HTTPException(status_code=503, detail="Auth introspection failed")
    user = response.json()
    email = user.get("email")
    if not email:
        raise HTTPException(status_code=401, detail="Session has no email claim")
    identity = {"email": str(email).lower(), "sub": str(user.get("id", ""))}
    _INTROSPECTION_CACHE[token] = (now, identity)
    return identity


async def _human_principal(
    session: AsyncSession, token: str
) -> tuple[Tenant, User | None]:
    identity = await _verify_supabase_session(token)
    email = identity["email"]

    user_row = (
        await session.execute(select(User).where(User.email == email))
    ).scalar_one_or_none()
    if user_row is not None:
        await bind_tenant(session, user_row.tenant_id)
        tenant = (
            await session.execute(select(Tenant).where(Tenant.id == user_row.tenant_id))
        ).scalar_one()
        return tenant, user_row

    # first login: the signup email is the owner — provision their row
    tenant = (
        await session.execute(select(Tenant).where(Tenant.owner_email == email))
    ).scalar_one_or_none()
    if tenant is None:
        raise HTTPException(
            status_code=403,
            detail="This email isn't invited to any workspace yet",
        )
    await bind_tenant(session, tenant.id)
    user_row = User(
        tenant_id=tenant.id,
        email=email,
        name=email.split("@")[0],
        role=UserRole.OWNER,
    )
    session.add(user_row)
    await session.flush()
    logger.info("owner_provisioned", tenant_id=str(tenant.id), email=email)
    return tenant, user_row


async def _key_principal(
    session: AsyncSession, x_api_key: str
) -> tuple[Tenant, None]:
    key_hash = hashlib.sha256(x_api_key.encode()).hexdigest()
    key_row = (
        await session.execute(
            select(ApiKey).where(ApiKey.key_hash == key_hash, ApiKey.revoked_at.is_(None))
        )
    ).scalar_one_or_none()
    if key_row is None:
        raise HTTPException(status_code=401, detail="Invalid API key")
    await bind_tenant(session, key_row.tenant_id)
    tenant = (
        await session.execute(select(Tenant).where(Tenant.id == key_row.tenant_id))
    ).scalar_one_or_none()
    if tenant is None:
        raise HTTPException(status_code=401, detail="Invalid API key")
    key_row.last_used_at = datetime.now(UTC)
    return tenant, None


class Principal:
    """Who is acting: the tenant (RLS-bound) and, for humans, their row."""

    def __init__(self, tenant: Tenant, user: User | None):
        self.tenant = tenant
        self.user = user


async def require_principal(
    session: AsyncSession = Depends(get_session),
    x_api_key: str | None = Header(default=None),
    authorization: str | None = Header(default=None),
) -> Principal:
    """Human session (Bearer JWT) or machine key (X-API-Key) → principal."""
    if authorization and authorization.lower().startswith("bearer "):
        tenant, user = await _human_principal(session, authorization[7:].strip())
        return Principal(tenant, user)
    if x_api_key:
        tenant, _ = await _key_principal(session, x_api_key)
        return Principal(tenant, None)
    raise HTTPException(status_code=401, detail="Missing credentials")


async def require_tenant(
    session: AsyncSession = Depends(get_session),
    x_api_key: str | None = Header(default=None),
    authorization: str | None = Header(default=None),
) -> Tenant:
    principal = await require_principal(
        session,
        x_api_key=x_api_key,
        authorization=authorization,
    )
    return principal.tenant

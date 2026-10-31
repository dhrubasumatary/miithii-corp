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

import jwt as pyjwt
import structlog
from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import bind_tenant, get_session
from app.models import ApiKey, Tenant, User, UserRole

logger = structlog.get_logger(__name__)

_JWKS_CACHE: tuple[float, pyjwt.PyJWKClient] | None = None
_JWKS_TTL = 3600.0


def _jwks_client() -> pyjwt.PyJWKClient | None:
    global _JWKS_CACHE
    settings = get_settings()
    if not settings.supabase_url:
        return None
    now = time.time()
    if _JWKS_CACHE is None or now - _JWKS_CACHE[0] > _JWKS_TTL:
        url = f"{settings.supabase_url.rstrip('/')}/auth/v1/jwks"
        _JWKS_CACHE = (now, pyjwt.PyJWKClient(url))
    return _JWKS_CACHE[1]


def _verify_supabase_jwt(token: str) -> dict:
    client = _jwks_client()
    if client is None:
        raise HTTPException(status_code=503, detail="Human sign-in not configured")
    try:
        signing_key = client.get_signing_key_from_jwt(token)
        claims = pyjwt.decode(
            token,
            signing_key.key,
            algorithms=["ES256", "RS256", "HS256"],
            options={"verify_aud": False},
        )
    except pyjwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail="Invalid session token") from exc
    email = claims.get("email")
    if not email:
        raise HTTPException(status_code=401, detail="Session has no email claim")
    return {"email": str(email).lower(), "sub": str(claims.get("sub", ""))}


async def _human_principal(
    session: AsyncSession, token: str
) -> tuple[Tenant, User | None]:
    identity = _verify_supabase_jwt(token)
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

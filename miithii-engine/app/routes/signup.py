"""POST /v1/signup — self-provisioning (gap #1).

A stranger creates a workspace: tenant + owner email + API key, minted once.
Runs on the ADMIN session (provisioning path — RLS blocks unbound app-role
inserts, exactly as the audit found). Guards: honeypot field, per-IP rate
limit (3/hour), one workspace per email (unique partial index, migration 0003).
No email verification yet — that lands with human identity (gap #2).
"""

import hashlib
import re
import secrets
import uuid

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, insert, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_admin_session
from app.models import ApiKey, Tenant

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/v1/signup", tags=["signup"])

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_HOURLY_LIMIT = 3


class SignupPayload(BaseModel):
    company: str = Field(min_length=2, max_length=100)
    email: str = Field(min_length=5, max_length=320)
    # honeypot — hidden field, humans never fill it, bots do
    website: str | None = Field(default=None, max_length=200)


def _slugify(company: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", company.lower()).strip("-")
    return (slug or "workspace")[:60] + "-" + secrets.token_hex(3)


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    return (forwarded.split(",")[0].strip() if forwarded else None) or (
        request.client.host if request.client else "unknown"
    )


@router.post("")
async def signup(
    payload: SignupPayload,
    request: Request,
    admin_session: AsyncSession = Depends(get_admin_session),
) -> dict:
    if payload.website:  # honeypot tripped
        raise HTTPException(status_code=400, detail="Signup rejected")

    email = payload.email.strip().lower()
    if not _EMAIL_RE.match(email):
        raise HTTPException(status_code=400, detail="Enter a valid email address")

    ip = _client_ip(request)
    recent = (
        await admin_session.execute(
            select(func.count())
            .select_from(Tenant)
            .where(Tenant.signup_ip == ip, text("tenants.created_at >= now() - interval '1 hour'"))
        )
    ).scalar_one()
    if recent >= _HOURLY_LIMIT:
        raise HTTPException(
            status_code=429,
            detail="Too many signups from this address — try again later",
        )

    existing = (
        await admin_session.execute(
            select(Tenant.id).where(Tenant.owner_email == email)
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=409,
            detail="This email already has a workspace — sign in with its key",
        )

    tenant_id = uuid.uuid4()
    raw_key = "mii_" + secrets.token_urlsafe(24)
    await admin_session.execute(
        insert(Tenant).values(
            id=tenant_id,
            name=payload.company.strip(),
            slug=_slugify(payload.company),
            owner_email=email,
            signup_ip=ip,
        )
    )
    await admin_session.execute(
        insert(ApiKey).values(
            tenant_id=tenant_id,
            name="owner key",
            key_hash=hashlib.sha256(raw_key.encode()).hexdigest(),
        )
    )
    await admin_session.commit()
    logger.info("workspace_provisioned", tenant_id=str(tenant_id), email=email)

    return {"tenant_id": str(tenant_id), "api_key": raw_key}

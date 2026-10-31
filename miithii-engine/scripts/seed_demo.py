"""Seed the CloudDesk demo tenant and mint an API key (printed ONCE).

Idempotent on the tenant slug; each run adds a fresh key. Uses the ADMIN
role (bypasses RLS) — this is provisioning, not a request path.
"""

import asyncio
import hashlib
import secrets

from sqlalchemy import insert, select

from app.config import get_settings
from app.db import create_db_engine
from app.models import ApiKey, Tenant

SLUG = "clouddesk-demo"


async def main() -> None:
    engine = create_db_engine(get_settings().database_url_admin)
    async with engine.begin() as conn:
        tenant_id = (
            await conn.execute(select(Tenant.id).where(Tenant.slug == SLUG))
        ).scalar_one_or_none()
        if tenant_id is None:
            result = await conn.execute(
                insert(Tenant)
                .values(name="CloudDesk (demo)", slug=SLUG)
                .returning(Tenant.id)
            )
            tenant_id = result.scalar_one()
            print(f"tenant created: {SLUG} ({tenant_id})")
        else:
            print(f"tenant exists: {SLUG} ({tenant_id})")

        raw_key = "mii_" + secrets.token_urlsafe(24)
        await conn.execute(
            insert(ApiKey).values(
                tenant_id=tenant_id,
                name="demo key",
                key_hash=hashlib.sha256(raw_key.encode()).hexdigest(),
            )
        )
    await engine.dispose()

    print()
    print("API key (copy now — shown only here):")
    print(raw_key)


if __name__ == "__main__":
    asyncio.run(main())

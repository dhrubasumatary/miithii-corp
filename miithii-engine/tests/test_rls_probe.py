"""RLS tenant-isolation probe against the REAL schema (ADR-003).

Runs as the miithii_app role (CI provisions it; locally scripts/provision_app_role.py
set it up). The probe fails loudly if any of these ever stop holding:
  - tenant A sees only A's rows, B only B's
  - no tenant bound -> zero rows (fail closed)
  - cross-tenant UPDATE touches 0 rows
Requires migration 0001 to have run (CI: alembic upgrade head before pytest).
"""

import uuid

import pytest
import sqlalchemy as sa
from sqlalchemy import insert, text, update

from app.config import get_settings
from app.db import create_db_engine
from app.models import Tenant, Ticket

SETTINGS = get_settings()
pytestmark = pytest.mark.skipif(
    SETTINGS.database_url is None,
    reason="DATABASE_URL (app role) not configured",
)


async def test_tenant_isolation():
    engine = create_db_engine(SETTINGS.database_url)
    admin_engine = (
        create_db_engine(SETTINGS.database_url_admin) if SETTINGS.database_url_admin else None
    )
    tid_a, tid_b = uuid.uuid4(), uuid.uuid4()
    ticket_a = [uuid.uuid4(), uuid.uuid4()]
    ticket_b = uuid.uuid4()

    try:
        async with engine.begin() as conn:
            await conn.execute(
                text("SELECT set_config('app.current_tenant', :t, false)"), {"t": str(tid_a)}
            )
            await conn.execute(
                insert(Tenant).values(id=tid_a, name="Probe A", slug=f"probe-a-{tid_a.hex[:8]}")
            )
            await conn.execute(
                insert(Ticket).values(
                    [
                        {"id": ticket_a[0], "tenant_id": tid_a, "subject": "a1", "body": "a1"},
                        {"id": ticket_a[1], "tenant_id": tid_a, "subject": "a2", "body": "a2"},
                    ]
                )
            )

        async with engine.begin() as conn:
            await conn.execute(
                text("SELECT set_config('app.current_tenant', :t, false)"), {"t": str(tid_b)}
            )
            await conn.execute(
                insert(Tenant).values(id=tid_b, name="Probe B", slug=f"probe-b-{tid_b.hex[:8]}")
            )
            await conn.execute(
                insert(Ticket).values(id=ticket_b, tenant_id=tid_b, subject="b1", body="b1")
            )

        async def visible_ids(tenant_id: uuid.UUID | None) -> list[str]:
            async with engine.connect() as conn:
                if tenant_id is None:
                    await conn.execute(text("SELECT set_config('app.current_tenant', '', false)"))
                else:
                    await conn.execute(
                        text("SELECT set_config('app.current_tenant', :t, false)"),
                        {"t": str(tenant_id)},
                    )
                rows = (await conn.execute(sa.select(Ticket.id))).scalars().all()
                return sorted(str(r) for r in rows)

        # A sees only A, B sees only B
        assert visible_ids.__name__  # noqa: B018 - readability marker
        assert (await visible_ids(tid_a)) == sorted(str(i) for i in ticket_a)
        assert (await visible_ids(tid_b)) == [str(ticket_b)]

        # no tenant bound -> zero rows (fail closed)
        assert (await visible_ids(None)) == []

        # cross-tenant UPDATE touches 0 rows
        async with engine.begin() as conn:
            await conn.execute(
                text("SELECT set_config('app.current_tenant', :t, false)"), {"t": str(tid_a)}
            )
            result = await conn.execute(
                update(Ticket).where(Ticket.id == ticket_b).values(subject="hacked")
            )
            assert result.rowcount == 0

    finally:
        if admin_engine is not None:
            async with admin_engine.begin() as conn:
                await conn.execute(
                    text("DELETE FROM tickets WHERE tenant_id IN (:a, :b)"),
                    {"a": str(tid_a), "b": str(tid_b)},
                )
                await conn.execute(
                    text("DELETE FROM tenants WHERE id IN (:a, :b)"),
                    {"a": str(tid_a), "b": str(tid_b)},
                )
            await admin_engine.dispose()
        await engine.dispose()

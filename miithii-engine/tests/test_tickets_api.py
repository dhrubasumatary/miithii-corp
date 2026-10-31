"""End-to-end API test against the REAL database (skips without DATABASE_URL).

Runs in deterministic mode (FORCE_DETERMINISTIC=1) — no network, no cost —
but the full stack: auth → tenant binding → RLS → pipeline → audit rows.
"""

import hashlib
import secrets
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, insert

from app.config import get_settings
from app.db import create_db_engine
from app.models import Analysis, ApiKey, Tenant, Ticket, UsageEvent

SETTINGS = get_settings()
pytestmark = pytest.mark.skipif(
    SETTINGS.database_url is None or SETTINGS.database_url_admin is None,
    reason="DATABASE_URL not configured",
)


async def test_create_and_read_ticket(monkeypatch):
    monkeypatch.setenv("FORCE_DETERMINISTIC", "1")
    get_settings.cache_clear()
    try:
        admin = create_db_engine(SETTINGS.database_url_admin)
        tenant_id, raw_key = uuid.uuid4(), "mii_test_" + secrets.token_urlsafe(18)
        async with admin.begin() as conn:
            await conn.execute(
                insert(Tenant).values(
                    id=tenant_id, name="API Test", slug=f"api-test-{tenant_id.hex[:8]}"
                )
            )
            await conn.execute(
                insert(ApiKey).values(
                    tenant_id=tenant_id,
                    name="test",
                    key_hash=hashlib.sha256(raw_key.encode()).hexdigest(),
                )
            )
        await admin.dispose()

        from app.main import create_app

        headers = {"X-API-Key": raw_key}
        try:
            with TestClient(create_app()) as client:
                response = client.post(
                    "/v1/tickets",
                    json={
                        "subject": "Production API is down",
                        "body": "All requests failing with 500 errors everywhere since the deploy.",
                    },
                    headers=headers,
                )
                assert response.status_code == 201, response.text
                body = response.json()
                assert body["action"] == "human_review"  # outage tag -> review
                assert body["requires_human"] is True

                analyses = client.get(
                    f"/v1/tickets/{body['ticket_id']}/analyses", headers=headers
                ).json()
                assert len(analyses) == 1
                assert analyses[0]["provider"] == "DeterministicProvider"

                # regression: the 500 the live browser QA caught — these routes
                # share require_tenant and must not fail on the key path
                assert client.get("/v1/knowledge", headers=headers).status_code == 200
                assert client.get("/v1/usage", headers=headers).status_code == 200

                # cross-tenant invisibility: a bogus key sees nothing of this tenant
                bogus = {"X-API-Key": "mii_" + secrets.token_urlsafe(18)}
                assert client.get("/v1/tickets", headers=bogus).status_code == 401
        finally:
            admin = create_db_engine(SETTINGS.database_url_admin)
            async with admin.begin() as conn:
                # FK-safe order: children first
                await conn.execute(delete(UsageEvent).where(UsageEvent.tenant_id == tenant_id))
                await conn.execute(delete(Analysis).where(Analysis.tenant_id == tenant_id))
                await conn.execute(delete(Ticket).where(Ticket.tenant_id == tenant_id))
                await conn.execute(delete(ApiKey).where(ApiKey.tenant_id == tenant_id))
                await conn.execute(delete(Tenant).where(Tenant.id == tenant_id))
            await admin.dispose()
    finally:
        get_settings.cache_clear()

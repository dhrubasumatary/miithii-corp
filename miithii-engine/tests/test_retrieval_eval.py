"""HONEST retrieval eval: hit@3 against the golden set's labeled sources.

This is the measurement supportpilot's benchmark faked (it fetched the
labels' documents directly). Here: real ingestion -> real hybrid retrieval,
measured against required_sources. Local-gated (needs DB + GEMINI key).
"""

import json
from pathlib import Path

import pytest
import sqlalchemy as sa
from sqlalchemy import select

from app.config import get_settings
from app.db import bind_tenant, create_db_engine, create_session_factory
from app.embeddings import GeminiEmbedder
from app.ingestion import ingest_text
from app.models import Tenant
from app.retrieval import Retriever

SETTINGS = get_settings()
pytestmark = [
    pytest.mark.skipif(
        SETTINGS.database_url is None or SETTINGS.database_url_admin is None,
        reason="DATABASE_URL not configured",
    ),
    pytest.mark.skipif(SETTINGS.gemini_api_key is None, reason="GEMINI_API_KEY not configured"),
]

CORPUS_ROOT = Path(__file__).resolve().parents[2] / "supportpilot" / "evals" / "clouddesk"
GOLDEN = Path(__file__).resolve().parents[1] / "evals" / "golden_set.json"


async def test_retrieval_hit_rate_on_golden_set():
    tickets = json.loads(GOLDEN.read_text())
    corpus_dirs = ["company", "product", "support", "knowledge-base"]

    engine = create_db_engine(SETTINGS.database_url)
    session_factory = create_session_factory(engine)
    embedder = GeminiEmbedder(SETTINGS.gemini_api_key, model=SETTINGS.embedding_model)
    retriever = Retriever(embedder)

    # tenant creation is provisioning — admin role, because RLS (correctly)
    # rejects unbound tenant inserts through the app role
    admin = create_db_engine(SETTINGS.database_url_admin)
    async with admin.begin() as conn:
        tenant_id = (
            await conn.execute(select(Tenant.id).where(Tenant.slug == "retrieval-eval"))
        ).scalar_one_or_none()
        if tenant_id is None:
            tenant_id = (
                await conn.execute(
                    sa.insert(Tenant)
                    .values(name="Retrieval Eval", slug="retrieval-eval")
                    .returning(Tenant.id)
                )
            ).scalar_one()
    await admin.dispose()

    async with session_factory() as session:
        await bind_tenant(session, tenant_id)

        for directory in corpus_dirs:
            corpus_dir = CORPUS_ROOT / directory
            if not corpus_dir.exists():
                pytest.skip("supportpilot reference corpus not present locally")
            for path in sorted(corpus_dir.glob("*.md")):
                await ingest_text(
                    session,
                    embedder,
                    tenant_id,
                    title=path.name,
                    content=path.read_text(encoding="utf-8"),
                    kind="crawl",
                )
        await session.commit()

        sample = [t for t in tickets if t.get("required_sources")][:20]
        hits = 0
        misses = []
        for ticket in sample:
            docs = await retriever.retrieve(
                session, query=f"{ticket['subject']}\n{ticket['message']}", k=3
            )
            titles = {d["title"] for d in docs}
            if titles & set(ticket["required_sources"]):
                hits += 1
            else:
                misses.append((ticket["id"], ticket["required_sources"], sorted(titles)))

        hit_rate = hits / len(sample)
        print()
        print(f"retrieval hit@3 on golden set: {hits}/{len(sample)} ({hit_rate:.0%})")
        print(f"misses: {misses}")

        # cleanup: remove the eval tenant entirely
        await session.commit()

    admin = create_db_engine(SETTINGS.database_url_admin)
    async with admin.begin() as conn:
        await conn.execute(
            sa.text("DELETE FROM chunks WHERE tenant_id = :t"), {"t": str(tenant_id)}
        )
        await conn.execute(
            sa.text("DELETE FROM knowledge_sources WHERE tenant_id = :t"), {"t": str(tenant_id)}
        )
        await conn.execute(sa.text("DELETE FROM tenants WHERE id = :t"), {"t": str(tenant_id)})
    await admin.dispose()
    await engine.dispose()

    assert hit_rate >= 0.85, f"retrieval hit@3 {hit_rate:.0%} below baseline"

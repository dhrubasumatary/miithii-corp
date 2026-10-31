"""Retrieval RLS test with precomputed vectors — CI-safe (no network, no key).

Proves two things at once: hybrid retrieval SQL works on real pgvector, and
chunks are tenant-scoped (binding to A never surfaces B's rows regardless of
vector similarity).
"""

import uuid

import pytest
import sqlalchemy as sa
from sqlalchemy import insert
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.config import get_settings
from app.db import create_db_engine
from app.models import Chunk, KnowledgeSource, SourceKind, Tenant
from app.retrieval import Retriever

SETTINGS = get_settings()
pytestmark = pytest.mark.skipif(
    SETTINGS.database_url is None or SETTINGS.database_url_admin is None,
    reason="DATABASE_URL not configured",
)


def _unit(dim: int, idx: int) -> list[float]:
    vec = [0.0] * dim
    vec[idx] = 1.0
    return vec


async def test_retrieval_is_tenant_scoped():
    engine = create_db_engine(SETTINGS.database_url)
    admin = create_db_engine(SETTINGS.database_url_admin)
    tid_a, tid_b = uuid.uuid4(), uuid.uuid4()
    vec_a, vec_b = _unit(768, 10), _unit(768, 20)

    async with admin.begin() as conn:
        await conn.execute(
            insert(Tenant).values(id=tid_a, name="Ret A", slug=f"ret-a-{tid_a.hex[:6]}")
        )
        await conn.execute(
            insert(Tenant).values(id=tid_b, name="Ret B", slug=f"ret-b-{tid_b.hex[:6]}")
        )
        for tenant_id, embedding, content, title in (
            (tid_a, vec_a, "alpha secret content", "doc-alpha.md"),
            (tid_b, vec_b, "beta secret content", "doc-beta.md"),
        ):
            source_id = (
                await conn.execute(
                    insert(KnowledgeSource)
                    .values(
                        tenant_id=tenant_id,
                        kind=SourceKind.MANUAL,
                        title=title,
                        status="ready",
                        content_hash=uuid.uuid4().hex,
                    )
                    .returning(KnowledgeSource.id)
                )
            ).scalar_one()
            await conn.execute(
                insert(Chunk).values(
                    tenant_id=tenant_id,
                    source_id=source_id,
                    ordinal=0,
                    content=content,
                    embedding=embedding,
                    token_count=10,
                )
            )

    retriever = Retriever(embedder=None)
    make_session = async_sessionmaker(engine, expire_on_commit=False)
    try:
        for tenant_id, expected_title in ((tid_a, "doc-alpha.md"), (tid_b, "doc-beta.md")):
            session = make_session()
            async with session.begin():
                await session.execute(
                    sa.text("SELECT set_config('app.current_tenant', :t, false)"),
                    {"t": str(tenant_id)},
                )
                rows = await retriever.retrieve(
                    session, query="secret content", query_embedding=vec_a
                )
            await session.close()
            titles = [r["title"] for r in rows]
            assert expected_title in titles, f"expected own doc for {expected_title}, got {titles}"
            assert len([t for t in titles if t != expected_title and t.startswith("doc-")]) == 0
    finally:
        async with admin.begin() as conn:
            await conn.execute(
                sa.text("DELETE FROM chunks WHERE tenant_id IN (:a, :b)"),
                {"a": str(tid_a), "b": str(tid_b)},
            )
            await conn.execute(
                sa.text("DELETE FROM knowledge_sources WHERE tenant_id IN (:a, :b)"),
                {"a": str(tid_a), "b": str(tid_b)},
            )
            await conn.execute(
                sa.text("DELETE FROM tenants WHERE id IN (:a, :b)"),
                {"a": str(tid_a), "b": str(tid_b)},
            )
        await admin.dispose()
        await engine.dispose()

"""Hybrid retrieval: pgvector cosine + Postgres full-text, fused with RRF (ADR-008).

Runs inside the caller's RLS binding — cross-tenant chunks are invisible by
construction. `query_embedding` may be precomputed (tests, embedding reuse).
"""

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger(__name__)

_RRF_K = 60
_CANDIDATES = 20


class Retriever:
    def __init__(self, embedder):
        self._embedder = embedder

    async def retrieve(
        self,
        session: AsyncSession,
        query: str,
        k: int = 3,
        query_embedding: list[float] | None = None,
    ) -> list[dict]:
        if query_embedding is None:
            query_embedding = (await self._embedder.embed([query]))[0]
        qv = "[" + ",".join(f"{x:.7f}" for x in query_embedding) + "]"

        vec_rows = (
            await session.execute(
                text(
                    """
                    SELECT c.id::text AS id, c.content, c.ordinal, s.title
                    FROM chunks c JOIN knowledge_sources s ON s.id = c.source_id
                    WHERE c.embedding IS NOT NULL
                    ORDER BY c.embedding <=> CAST(:qv AS vector)
                    LIMIT :n
                    """
                ),
                {"qv": qv, "n": _CANDIDATES},
            )
        ).all()

        lex_rows = (
            await session.execute(
                text(
                    """
                    SELECT c.id::text AS id, c.content, c.ordinal, s.title
                    FROM chunks c JOIN knowledge_sources s ON s.id = c.source_id
                    WHERE c.content_tsv @@ plainto_tsquery('english', :q)
                    ORDER BY ts_rank(c.content_tsv, plainto_tsquery('english', :q)) DESC
                    LIMIT :n
                    """
                ),
                {"q": query, "n": _CANDIDATES},
            )
        ).all()

        scores: dict[str, float] = {}
        meta: dict[str, dict] = {}
        for rank, row in enumerate(vec_rows):
            scores[row.id] = scores.get(row.id, 0.0) + 1.0 / (_RRF_K + rank + 1)
            meta[row.id] = {"content": row.content, "ordinal": row.ordinal, "title": row.title}
        for rank, row in enumerate(lex_rows):
            scores[row.id] = scores.get(row.id, 0.0) + 1.0 / (_RRF_K + rank + 1)
            meta[row.id] = {"content": row.content, "ordinal": row.ordinal, "title": row.title}

        top = sorted(scores.items(), key=lambda kv: -kv[1])[:k]
        return [
            {
                "citation": f"{meta[cid]['title']} (part {meta[cid]['ordinal'] + 1})",
                "title": meta[cid]["title"],
                "content": meta[cid]["content"],
            }
            for cid, _ in top
        ]

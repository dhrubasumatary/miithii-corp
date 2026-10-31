"""/v1/knowledge — tenant knowledge ingestion (crawl + upload) and listing."""

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.ingestion import crawl as crawl_ingest
from app.ingestion import ingest_text
from app.models import Chunk, KnowledgeSource, SourceKind, Tenant
from app.security import require_tenant

router = APIRouter(prefix="/v1/knowledge", tags=["knowledge"])


class UploadPayload(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    content: str = Field(min_length=1, max_length=500_000)


class CrawlPayload(BaseModel):
    url: str = Field(min_length=8, max_length=2048)
    max_pages: int = Field(default=5, ge=1, le=10)


def _embedder(request: Request):
    embedder = request.app.state.embedder
    if embedder is None:
        raise HTTPException(status_code=503, detail="Embeddings not configured on this deployment")
    return embedder


@router.post("/upload", status_code=201)
async def upload_knowledge(
    payload: UploadPayload,
    request: Request,
    tenant: Tenant = Depends(require_tenant),
    session: AsyncSession = Depends(get_session),
) -> dict:
    source = await ingest_text(
        session,
        _embedder(request),
        tenant.id,
        title=payload.title,
        content=payload.content,
        kind=SourceKind.MANUAL,
    )
    await session.commit()
    return {"source_id": str(source.id), "status": source.status.value, "error": source.error}


@router.post("/crawl", status_code=201)
async def crawl_knowledge(
    payload: CrawlPayload,
    request: Request,
    tenant: Tenant = Depends(require_tenant),
    session: AsyncSession = Depends(get_session),
) -> dict:
    sources = await crawl_ingest(
        session, _embedder(request), tenant.id, payload.url, max_pages=payload.max_pages
    )
    await session.commit()
    return {
        "ingested": [
            {"source_id": str(s.id), "title": s.title, "status": s.status.value} for s in sources
        ]
    }


@router.get("")
async def list_knowledge(
    tenant: Tenant = Depends(require_tenant),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    rows = (
        await session.execute(
            select(
                KnowledgeSource.id,
                KnowledgeSource.title,
                KnowledgeSource.kind,
                KnowledgeSource.status,
                KnowledgeSource.origin_url,
                KnowledgeSource.created_at,
                func.count(Chunk.id).label("chunk_count"),
            )
            .outerjoin(Chunk, Chunk.source_id == KnowledgeSource.id)
            .where(KnowledgeSource.tenant_id == tenant.id)
            .group_by(KnowledgeSource.id)
            .order_by(KnowledgeSource.created_at.desc())
            .limit(100)
        )
    ).all()
    return [
        {
            "id": str(row.id),
            "title": row.title,
            "kind": row.kind.value,
            "status": row.status.value,
            "origin_url": row.origin_url,
            "chunks": row.chunk_count,
            "created_at": row.created_at.isoformat(),
        }
        for row in rows
    ]

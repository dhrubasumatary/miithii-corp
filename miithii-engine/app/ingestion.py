"""Ingestion: fetch/extract → chunk → embed → store (P3).

Tenant-scoped by construction — every row carries tenant_id and ingestion
runs inside the caller's RLS binding. v1 is synchronous in-request with a
page cap; background queueing is a P5+ upgrade (ADR-002: no Redis yet).
"""

import hashlib
import re
from datetime import UTC, datetime

import httpx
import structlog
from selectolax.lexbor import LexborHTMLParser
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Chunk, KnowledgeSource, SourceKind, SourceStatus

logger = structlog.get_logger(__name__)

_CHUNK_TARGET = 1200  # chars (~300 tokens) — spike showed chunk granularity matters
_UA = {"User-Agent": "Mozilla/5.0 (compatible; miithii-ingest/0.1)"}


def chunk_text(content: str) -> list[dict]:
    """Paragraph-aware chunking to ~_CHUNK_TARGET chars with light overlap."""
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", content) if p.strip()]
    chunks: list[str] = []
    current = ""
    for para in paragraphs:
        if len(current) + len(para) + 2 <= _CHUNK_TARGET or not current:
            current = f"{current}\n\n{para}".strip()
        else:
            chunks.append(current)
            current = para[-200:] if len(para) > _CHUNK_TARGET else para
    if current:
        chunks.append(current)
    return [{"text": c, "tokens": max(1, len(c) // 4)} for c in chunks]


def extract_main_text(html: str) -> str:
    tree = LexborHTMLParser(html)
    for node in tree.css("nav, header, footer, script, style, aside, noscript"):
        node.decompose()
    main = tree.css_first("main") or tree.css_first("article") or tree.body
    text = (main or tree).text(separator="\n")
    lines = [ln.strip() for ln in text.splitlines()]
    return "\n".join(ln for ln in lines if ln)


def _content_hash(content: str) -> str:
    return hashlib.sha256(content.encode()).hexdigest()


async def ingest_text(
    session: AsyncSession,
    embedder,
    tenant_id,
    title: str,
    content: str,
    kind: SourceKind = SourceKind.MANUAL,
    origin_url: str | None = None,
) -> KnowledgeSource:
    """Store one document + embedded chunks. Does NOT commit (caller owns tx)."""
    content_hash = _content_hash(content)

    existing = (
        await session.execute(
            select(KnowledgeSource).where(
                KnowledgeSource.tenant_id == tenant_id,
                KnowledgeSource.content_hash == content_hash,
                KnowledgeSource.status == SourceStatus.READY,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing  # idempotent re-ingest

    source = KnowledgeSource(
        tenant_id=tenant_id,
        kind=kind,
        title=title[:500],
        content_hash=content_hash,
        status=SourceStatus.PENDING,
        origin_url=origin_url,
    )
    session.add(source)
    await session.flush()

    try:
        pieces = chunk_text(content)
        vectors = await embedder.embed([p["text"] for p in pieces])
        for ordinal, (piece, vector) in enumerate(zip(pieces, vectors, strict=True)):
            session.add(
                Chunk(
                    tenant_id=tenant_id,
                    source_id=source.id,
                    ordinal=ordinal,
                    content=piece["text"],
                    embedding=vector,
                    token_count=piece["tokens"],
                )
            )
        source.status = SourceStatus.READY
    except Exception as exc:  # noqa: BLE001 - record and surface, never half-ready
        source.status = SourceStatus.FAILED
        source.error = str(exc)[:500]
        logger.warning("ingest_failed", title=title, error=str(exc)[:200])

    return source


async def fetch_and_extract(client: httpx.AsyncClient, url: str) -> tuple[str, str]:
    """Fetch a page; return (title, main text). Raises on non-200."""
    response = await client.get(url, headers=_UA, follow_redirects=True, timeout=30)
    if response.status_code != 200:
        raise RuntimeError(f"fetch {url} -> HTTP {response.status_code}")
    html = response.text
    tree = LexborHTMLParser(html)
    title_node = tree.css_first("title")
    title = title_node.text(strip=True) if title_node else url
    return title.strip()[:500], extract_main_text(html)


async def crawl(
    session: AsyncSession,
    embedder,
    tenant_id,
    url: str,
    max_pages: int = 5,
) -> list[KnowledgeSource]:
    """Crawl one URL, or a sitemap (URL ending in .xml) up to max_pages."""
    results: list[KnowledgeSource] = []
    async with httpx.AsyncClient() as client:
        if url.endswith(".xml"):
            response = await client.get(url, headers=_UA, follow_redirects=True, timeout=30)
            response.raise_for_status()
            locs = re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", response.text)
            locs = [u for u in locs if not u.endswith((".xml", ".zip"))][:max_pages]
        else:
            locs = [url]

        for loc in locs:
            try:
                title, text = await fetch_and_extract(client, loc)
                if len(text) < 200:
                    logger.warning("crawl_page_too_short", url=loc, chars=len(text))
                    continue
                results.append(
                    await ingest_text(
                        session,
                        embedder,
                        tenant_id,
                        title=title,
                        content=text,
                        kind=SourceKind.CRAWL,
                        origin_url=loc,
                    )
                )
            except Exception as exc:  # noqa: BLE001 - one bad page must not kill the crawl
                logger.warning("crawl_page_failed", url=loc, error=str(exc)[:200])
    return results


def note_failure(source: KnowledgeSource, error: str) -> None:
    source.status = SourceStatus.FAILED
    source.error = error[:500]
    source.updated_at = datetime.now(UTC)

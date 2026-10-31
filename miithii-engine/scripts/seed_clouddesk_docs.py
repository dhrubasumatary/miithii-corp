"""Ingest the CloudDesk demo documentation into the clouddesk-demo tenant.

Reads the markdown corpus from the local supportpilot clone (unpushed
reference repo) and ingests each file as a knowledge source. Requires
GEMINI_API_KEY (embeddings) and the schema to be migrated.
"""

import asyncio
import sys
from pathlib import Path

from sqlalchemy import select

from app.config import get_settings
from app.db import bind_tenant, create_db_engine, create_session_factory
from app.ingestion import ingest_text
from app.models import Tenant

REPO_ROOT = Path(__file__).resolve().parents[2]
CORPUS_DIRS = ["company", "product", "support", "knowledge-base"]


async def seed(tenant_slug: str = "clouddesk-demo") -> int:
    settings = get_settings()
    engine = create_db_engine(settings.database_url)
    session_factory = create_session_factory(engine)

    from app.embeddings import GeminiEmbedder

    embedder = GeminiEmbedder(settings.gemini_api_key, model=settings.embedding_model)

    # tenant lookup is provisioning -> admin role (RLS blocks unbound reads)
    admin = create_db_engine(settings.database_url_admin)
    async with admin.connect() as conn:
        tenant_id = (
            await conn.execute(select(Tenant.id).where(Tenant.slug == tenant_slug))
        ).scalar_one_or_none()
    await admin.dispose()
    if tenant_id is None:
        raise SystemExit(f"tenant '{tenant_slug}' not found — run scripts/seed_demo.py first")

    count = 0
    async with session_factory() as session:
        await bind_tenant(session, tenant_id)

        for directory in CORPUS_DIRS:
            corpus_dir = REPO_ROOT / "supportpilot" / "evals" / "clouddesk" / directory
            if not corpus_dir.exists():
                print(f"missing corpus dir (reference repo absent?): {corpus_dir}")
                continue
            for path in sorted(corpus_dir.glob("*.md")):
                content = path.read_text(encoding="utf-8")
                source = await ingest_text(
                    session,
                    embedder,
                    tenant_id,
                    title=path.name,
                    content=content,
                    kind="crawl",
                )
                await session.commit()
                count += 1
                print(f"  {source.status.value:<7} {path.name} ({len(content)} chars)")
    await engine.dispose()
    return count


if __name__ == "__main__":
    total = asyncio.run(seed(sys.argv[1] if len(sys.argv) > 1 else "clouddesk-demo"))
    print(f"done: {total} sources processed")

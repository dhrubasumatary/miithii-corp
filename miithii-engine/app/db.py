"""Async database engine and session factory (ADR-002).

Note on pooling: the dev/prod Supabase URL uses the SESSION pooler (port 5432),
which preserves session state (`SET app.current_tenant` for RLS, ADR-003).
Do NOT swap to the transaction pooler (:6543) without revisiting RLS binding.
"""

from collections.abc import AsyncIterator

from fastapi import Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


def create_db_engine(database_url: str) -> AsyncEngine:
    """Create the async engine, pinning the asyncpg driver explicitly.

    A bare `postgresql://` URL makes SQLAlchemy's async engine default to the
    psycopg3 dialect (and crash on import). The .env keeps the Supabase-style
    `postgresql://` form; we normalize here so the driver is never implicit.
    """
    url = database_url
    if url.startswith("postgresql://"):
        url = "postgresql+asyncpg://" + url.removeprefix("postgresql://")
    return create_async_engine(url, pool_pre_ping=True)


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    """FastAPI dependency: one session per request, from lifespan-managed engine."""
    factory: async_sessionmaker[AsyncSession] = request.app.state.session_factory
    async with factory() as session:
        yield session


async def bind_tenant(session: AsyncSession, tenant_id) -> None:
    """Bind the RLS tenant for this session's transactions (ADR-003).

    Every request binds explicitly — we never rely on pooler state resets.
    The session pooler (session mode) runs DISCARD ALL on release, but the
    binding here is the contract, not the reset.
    """
    await session.execute(
        text("SELECT set_config('app.current_tenant', :tid, false)"),
        {"tid": str(tenant_id)},
    )

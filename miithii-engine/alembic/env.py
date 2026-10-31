"""Alembic async environment. Migrations run as the ADMIN role.

The URL is passed straight to the engine (never through configparser) —
percent-encoded passwords in pooler URLs break ConfigParser interpolation.
"""

import asyncio
import os
from collections.abc import Sequence

from alembic import context

from app.config import get_settings
from app.db import create_db_engine
from app.models import Base

config = context.config

_url = os.getenv("ALEMBIC_DATABASE_URL") or get_settings().database_url_admin
if not _url:
    raise RuntimeError("No admin database URL: set DATABASE_URL_ADMIN (or ALEMBIC_DATABASE_URL)")

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    connectable = create_db_engine(_url)
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())

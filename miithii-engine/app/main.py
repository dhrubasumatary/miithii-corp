"""MIITHII Engine — FastAPI application factory.

Everything request-scoped is built inside lifespan (ADR/builder rule: no
import-time singletons, no filesystem-path tricks). The app object at the
bottom exists only as the uvicorn entrypoint (`app.main:app`).
"""

from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.db import create_db_engine, create_session_factory
from app.logging_config import configure_logging
from app.middleware import RequestContextMiddleware
from app.routes.health import router as health_router

logger = structlog.get_logger(__name__)


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if settings.database_url:
            engine = create_db_engine(settings.database_url)
            app.state.engine = engine
            app.state.session_factory = create_session_factory(engine)
            logger.info("db_engine_started")
        else:
            logger.warning("db_not_configured")
        yield
        if getattr(app.state, "engine", None) is not None:
            await app.state.engine.dispose()
            logger.info("db_engine_disposed")

    app = FastAPI(
        title="MIITHII Engine",
        description="Internal support copilot — policy-gated AI pipeline",
        version=settings.service_version,
        lifespan=lifespan,
    )

    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[origin.strip() for origin in settings.cors_origins.split(",")],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health_router)
    return app


app = create_app()

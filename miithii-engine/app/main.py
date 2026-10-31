"""MIITHII Engine — FastAPI application factory.

Everything request-scoped is built inside lifespan (no import-time
singletons, no filesystem-path tricks). The module-level `app` exists only
as the uvicorn entrypoint (`app.main:app`).
"""

from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.db import create_db_engine, create_session_factory
from app.logging_config import configure_logging
from app.middleware import RequestContextMiddleware
from app.pipeline import TicketAnalyzer
from app.providers.aimlapi import AIMLAPIProvider
from app.providers.base import Provider
from app.providers.deterministic import DeterministicProvider
from app.providers.failover import FailoverProvider
from app.providers.gemini import GeminiProvider
from app.routes.health import router as health_router
from app.routes.tickets import router as tickets_router

logger = structlog.get_logger(__name__)


def _build_provider(settings) -> Provider:
    if settings.force_deterministic:
        return DeterministicProvider()
    chain: list[Provider] = []
    if settings.aimlapi_api_key:
        chain.append(
            AIMLAPIProvider(
                api_key=settings.aimlapi_api_key,
                model=settings.aimlapi_model,
                base_url=settings.aimlapi_base_url,
                timeout_s=settings.aimlapi_timeout_s,
            )
        )
    if settings.gemini_api_key:
        chain.append(
            GeminiProvider(
                api_key=settings.gemini_api_key,
                model=settings.gemini_model,
                timeout_s=settings.draft_timeout_s,
            )
        )
    if not chain:
        logger.warning("no_llm_provider_configured_deterministic_only")
        return DeterministicProvider()
    if len(chain) == 1:
        return chain[0]
    return FailoverProvider(chain)


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.analyzer = TicketAnalyzer(
            provider=_build_provider(settings),
            confidence_threshold=settings.classifier_confidence_threshold,
        )
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
    app.include_router(tickets_router)
    return app


app = create_app()

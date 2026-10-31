"""FailoverProvider — tries a provider chain in order, first success wins (ADR-006).

Chain shape set by config; the pipeline's deterministic fallback remains the
final layer behind this (fail closed, never open).
"""

import structlog

from app.domain import ClassifierResult, DraftContext, DraftResult
from app.providers.base import Provider, ProviderError

logger = structlog.get_logger(__name__)


class FailoverProvider(Provider):
    def __init__(self, providers: list[Provider]):
        if not providers:
            raise ValueError("FailoverProvider needs at least one provider")
        self._providers = providers

    async def _run(self, method_name: str, *args):
        errors: list[str] = []
        for provider in self._providers:
            try:
                return await getattr(provider, method_name)(*args)
            except ProviderError as exc:
                errors.append(f"{type(provider).__name__}: {exc}")
                logger.warning("failover_advancing", failed=type(provider).__name__, error=str(exc))
        raise ProviderError("; ".join(errors) or "no providers configured")

    async def classify(self, subject: str, body: str) -> ClassifierResult | None:
        return await self._run("classify", subject, body)

    async def draft(self, context: DraftContext) -> DraftResult:
        return await self._run("draft", context)

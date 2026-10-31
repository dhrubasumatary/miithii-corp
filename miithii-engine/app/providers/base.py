"""Provider ABC (ADR-006) — the only LLM surface the rest of the engine sees.

Vendor SDKs live behind this contract; adapters own their own error mapping.
"""

from abc import ABC, abstractmethod

from app.domain import ClassifierResult, DraftContext, DraftResult


class ProviderError(RuntimeError):
    """Base class for provider failures (mapped to 5xx upstream, never 4xx)."""


class ProviderRateLimitError(ProviderError):
    """Quota/rate limit exceeded — retryable with backoff."""


class ProviderUnavailableError(ProviderError):
    """Provider temporarily down (5xx) or timed out — retryable, then fallback."""


class Provider(ABC):
    @abstractmethod
    async def classify(self, subject: str, body: str) -> ClassifierResult | None:
        """LLM classification, or None to let the keyword pre-pass decide."""

    @abstractmethod
    async def draft(self, context: DraftContext) -> DraftResult:
        """Customer-facing draft within the policy action. MUST NOT fail open:
        on unrecoverable error the pipeline degrades to the deterministic provider."""

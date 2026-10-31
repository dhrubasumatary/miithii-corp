"""AIML API adapter (OpenAI-compatible aggregator) — adapter #2 (ADR-006).

Uses plain httpx against the OpenAI chat-completions shape; no vendor SDK.
Verified live: `google/gemini-flash-latest` is a THINKING model — reasoning
tokens consume max_tokens before content appears, so the budget is generous
and empty content is treated as a retryable provider error.
"""

import asyncio
import json

import httpx
import structlog

from app.domain import ClassifierResult, DraftContext, DraftResult
from app.providers.base import (
    Provider,
    ProviderError,
    ProviderRateLimitError,
    ProviderUnavailableError,
)
from app.providers.prompts import CLASSIFY_PROMPT, DRAFT_PROMPT

logger = structlog.get_logger(__name__)

_MAX_ATTEMPTS = 3


class AIMLAPIProvider(Provider):
    def __init__(
        self,
        api_key: str,
        model: str = "google/gemini-flash-latest",
        base_url: str = "https://api.aimlapi.com/v1",
        timeout_s: float = 60.0,
        max_tokens: int = 2048,
    ):
        self._api_key = api_key
        self._model = model
        self._base_url = base_url.rstrip("/")
        self._timeout_s = timeout_s
        self._max_tokens = max_tokens

    async def _complete(self, prompt: str, schema_name: str, schema: dict) -> dict:
        payload = {
            "model": self._model,
            "messages": [{"role": "user", "content": prompt}],
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": schema_name, "schema": schema, "strict": True},
            },
            "max_tokens": self._max_tokens,
        }
        headers = {"Authorization": f"Bearer {self._api_key}"}

        last: Exception | None = None
        for attempt in range(_MAX_ATTEMPTS):
            try:
                async with httpx.AsyncClient(timeout=self._timeout_s) as client:
                    response = await client.post(
                        f"{self._base_url}/chat/completions", json=payload, headers=headers
                    )
            except httpx.TimeoutException:
                last = ProviderUnavailableError("aimlapi timeout")
                logger.warning("provider_timeout", attempt=attempt + 1)
            except httpx.HTTPError as exc:
                last = ProviderUnavailableError(f"aimlapi transport error: {exc}")
                logger.warning("provider_transport_error", attempt=attempt + 1)
            else:
                if response.status_code == 429:
                    last = ProviderRateLimitError("aimlapi rate limited")
                    logger.warning("provider_rate_limited", attempt=attempt + 1)
                elif response.status_code >= 500:
                    last = ProviderUnavailableError(f"aimlapi {response.status_code}")
                    logger.warning("provider_unavailable", attempt=attempt + 1)
                elif response.status_code >= 400:
                    raise ProviderError(
                        f"aimlapi client error {response.status_code}: {response.text[:200]}"
                    )
                else:
                    choices = response.json().get("choices") or [{}]
                    content = choices[0].get("message", {}).get("content")
                    if not content or not str(content).strip():
                        # thinking models can burn the token budget on reasoning
                        last = ProviderError("aimlapi empty content (reasoning budget exhausted)")
                        logger.warning("provider_empty_content", attempt=attempt + 1)
                    else:
                        return self._parse_json(str(content))
            if attempt < _MAX_ATTEMPTS - 1:
                await asyncio.sleep(2**attempt)
        assert last is not None
        raise last

    @staticmethod
    def _parse_json(text: str) -> dict:
        cleaned = text.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise ProviderError("aimlapi returned invalid JSON") from exc

    async def classify(self, subject: str, body: str) -> ClassifierResult | None:
        prompt = CLASSIFY_PROMPT.format(subject=subject, body=body)
        data = await self._complete(prompt, "classify", ClassifierResult.model_json_schema())
        return ClassifierResult.model_validate(data)

    async def draft(self, context: DraftContext) -> DraftResult:
        documents = (
            "\n\n".join(f"--- {name} ---\n{content}" for name, content in context.documents.items())
            or "(no knowledge documents retrieved)"
        )
        prompt = DRAFT_PROMPT.format(
            action=context.action.value,
            flags=", ".join(context.flags) or "none",
            subject=context.subject,
            body=context.body,
            documents=documents,
        )
        data = await self._complete(prompt, "draft", DraftResult.model_json_schema())
        return DraftResult.model_validate(data)

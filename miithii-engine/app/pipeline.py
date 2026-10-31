"""TicketAnalyzer — the pipeline (ADR-004/005/006).

classify (keyword canary + LLM refinement) → deterministic PolicyEngine →
LLM draft → content validation → PERSIST audit rows → respond.
LLM failures degrade to the deterministic provider; they never fail open.
"""

import time

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.classifier import KeywordClassifier
from app.domain import (
    AnalysisResponse,
    ClassifierResult,
    DraftContext,
    PolicyDecision,
)
from app.models import Analysis, Tenant, Ticket, TicketStatus, UsageEvent
from app.policy import PolicyEngine
from app.providers.base import Provider, ProviderError
from app.providers.deterministic import DeterministicProvider
from app.providers.validator import validate_draft

logger = structlog.get_logger(__name__)

_PROMPT_VERSION = "draft-v1"


class TicketAnalyzer:
    def __init__(self, provider: Provider, confidence_threshold: float = 0.6):
        self._provider = provider
        self._keyword = KeywordClassifier()
        self._policy = PolicyEngine()
        self._confidence_threshold = confidence_threshold
        self._fallback = DeterministicProvider()

    async def analyze(
        self,
        session: AsyncSession,
        tenant: Tenant,
        subject: str,
        body: str,
        request_id: str | None = None,
        documents: dict[str, str] | None = None,
    ) -> AnalysisResponse:
        start = time.perf_counter()

        # 1) classify: keyword canary (always) + LLM refinement (best effort)
        keyword = self._keyword.classify(subject, body)
        tags = list(keyword.tags)
        category = keyword.category
        severity = keyword.severity
        difficulty = keyword.difficulty

        llm_result: ClassifierResult | None = None
        provider_name = type(self._provider).__name__
        try:
            llm_result = await self._provider.classify(subject, body)
        except ProviderError as exc:
            logger.warning("classify_provider_failed", error=str(exc))

        if llm_result is not None:
            tags = sorted(set(tags) | set(llm_result.tags))
            if llm_result.confidence >= self._confidence_threshold:
                category = llm_result.category
                severity = llm_result.severity
                difficulty = llm_result.difficulty
            else:
                tags.append("ambiguous")  # low confidence -> CLARIFY path (ADR-007)

        # 2) policy — deterministic, authoritative
        decision: PolicyDecision = self._policy.evaluate(tags, tenant.policy_config)

        # 3) draft (LLM) with deterministic fallback, then validate
        context = DraftContext(
            subject=subject, body=body, action=decision.action,
            flags=decision.flags, documents=documents or {},
        )
        draft = None
        used_provider = provider_name
        used_model = getattr(self._provider, "_model", "deterministic")
        try:
            draft = await self._provider.draft(context)
        except ProviderError as exc:
            logger.warning("draft_provider_failed_falling_back", error=str(exc))

        if draft is None:
            draft = await self._fallback.draft(context)
            used_provider = "DeterministicProvider"
            used_model = "deterministic"
        try:
            draft = validate_draft(decision, draft)
        except ValueError as exc:
            logger.warning("draft_validation_failed_falling_back", error=str(exc))
            draft = await self._fallback.draft(context)
            used_provider = "DeterministicProvider"
            used_model = "deterministic"

        latency_ms = int((time.perf_counter() - start) * 1000)

        # 4) persist — audit BEFORE responding (ADR-005)
        ticket = Ticket(
            tenant_id=tenant.id,
            subject=subject,
            body=body,
            status=TicketStatus.ESCALATED if decision.requires_human else TicketStatus.ANSWERED,
        )
        session.add(ticket)
        await session.flush()

        analysis = Analysis(
            tenant_id=tenant.id,
            ticket_id=ticket.id,
            category=category.value,
            severity=severity.value,
            difficulty=difficulty.value,
            action=decision.action.value,
            answer=draft.answer,
            policy_flags=decision.flags,
            citations=[],
            confidence=draft.confidence,
            latency_ms=latency_ms,
            prompt_tokens=draft.prompt_tokens,
            completion_tokens=draft.completion_tokens,
            provider=used_provider,
            model=used_model,
            prompt_version=_PROMPT_VERSION,
        )
        session.add(analysis)
        session.add(
            UsageEvent(
                tenant_id=tenant.id,
                kind="draft",
                provider=used_provider,
                model=used_model,
                prompt_tokens=draft.prompt_tokens,
                completion_tokens=draft.completion_tokens,
                latency_ms=latency_ms,
                request_id=request_id,
            )
        )
        await session.commit()

        logger.info(
            "ticket_analyzed",
            ticket_id=str(ticket.id),
            action=decision.action.value,
            requires_human=decision.requires_human,
            latency_ms=latency_ms,
        )
        return AnalysisResponse(
            ticket_id=str(ticket.id),
            category=category.value,
            severity=severity.value,
            difficulty=difficulty.value,
            action=decision.action.value,
            answer=draft.answer,
            requires_human=decision.requires_human,
            policy_flags=decision.flags,
            citations=[],
            confidence=draft.confidence,
            latency_ms=latency_ms,
        )

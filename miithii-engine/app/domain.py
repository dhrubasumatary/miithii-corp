"""Domain contracts — enums and Pydantic models shared across the pipeline."""

from enum import StrEnum

from pydantic import BaseModel, Field


class TicketCategory(StrEnum):
    BILLING = "billing"
    TECHNICAL_API = "technical_api"
    ACCOUNT_AUTHENTICATION = "account_authentication"
    PERMISSIONS_SECURITY = "permissions_security"
    INTEGRATIONS = "integrations"
    PRODUCT_HOW_TO = "product_how_to"
    REFUND_CANCELLATION = "refund_cancellation"
    FEATURE_REQUEST = "feature_request"


class TicketSeverity(StrEnum):
    P0 = "P0"
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"


class TicketDifficulty(StrEnum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class Action(StrEnum):
    ANSWER = "answer"
    HUMAN_REVIEW = "human_review"
    REFUSE_AND_GUIDE = "refuse_and_guide"
    REFUSE = "refuse"
    ESCALATE = "escalate"
    REFUSE_AND_ESCALATE = "refuse_and_escalate"
    CLARIFY = "clarify"


class ClassifierResult(BaseModel):
    category: TicketCategory
    severity: TicketSeverity = TicketSeverity.P3
    difficulty: TicketDifficulty = TicketDifficulty.EASY
    tags: list[str] = Field(default_factory=list)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    prompt_tokens: int | None = None
    completion_tokens: int | None = None


class PolicyDecision(BaseModel):
    """Emitted by the deterministic PolicyEngine — the ONLY source of the action."""

    action: Action
    requires_human: bool = False
    flags: list[str] = Field(default_factory=list)


class DraftContext(BaseModel):
    subject: str
    body: str
    action: Action
    flags: list[str] = Field(default_factory=list)
    documents: dict[str, str] = Field(default_factory=dict)


class DraftResult(BaseModel):
    """The LLM's customer-facing draft. Deliberately has NO action field —
    the LLM cannot express an action, so it cannot override one (ADR-004)."""

    answer: str
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    prompt_tokens: int | None = None
    completion_tokens: int | None = None


class TicketCreate(BaseModel):
    subject: str = Field(min_length=1, max_length=500)
    body: str = Field(min_length=1, max_length=10000)
    external_ref: str | None = Field(default=None, max_length=200)


class AnalysisResponse(BaseModel):
    ticket_id: str
    category: str
    severity: str
    difficulty: str
    action: str
    answer: str | None = None
    requires_human: bool = False
    policy_flags: list[str] = Field(default_factory=list)
    citations: list[str] = Field(default_factory=list)
    confidence: float | None = None
    latency_ms: int | None = None
    # the receipt: what the run actually spent. Measured, not estimated —
    # the dashboard renders these as fine print on every reply.
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    cost_usd: float | None = None

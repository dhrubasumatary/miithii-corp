"""SQLAlchemy 2.0 models — ADR-002 schema.

Every tenant-scoped table carries tenant_id; RLS policies (migration 0001)
enforce isolation via the app.current_tenant session variable (ADR-003).
Enums are stored as VARCHAR + check (native_enum=False) so adding members
is a migration-free change.
"""

import uuid
from datetime import datetime
from enum import StrEnum

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Computed,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    Uuid,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


def _enum(enum_cls) -> Enum:
    return Enum(
        enum_cls, native_enum=False, length=32, values_callable=lambda c: [m.value for m in c]
    )


class TenantPlan(StrEnum):
    FREE = "free"
    PRO = "pro"


class LlmTier(StrEnum):
    """PII guardrail (ledger #11): tenant data only ever rides paid_tier."""

    FREE_TIER = "free_tier"
    PAID_TIER = "paid_tier"


class SourceKind(StrEnum):
    CRAWL = "crawl"
    UPLOAD = "upload"
    MANUAL = "manual"


class SourceStatus(StrEnum):
    PENDING = "pending"
    READY = "ready"
    FAILED = "failed"


class TicketStatus(StrEnum):
    NEW = "new"
    ANALYZING = "analyzing"
    ANSWERED = "answered"
    ESCALATED = "escalated"
    CLOSED = "closed"


class MessageRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"
    AGENT_NOTE = "agent_note"


class UserRole(StrEnum):
    OWNER = "owner"
    ADMIN = "admin"
    AGENT = "agent"


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Tenant(Base, TimestampMixin):
    __tablename__ = "tenants"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, server_default=text("gen_random_uuid()")
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    plan: Mapped[TenantPlan] = mapped_column(
        _enum(TenantPlan), default=TenantPlan.FREE, server_default="free", nullable=False
    )
    llm_tier: Mapped[LlmTier] = mapped_column(
        _enum(LlmTier), default=LlmTier.PAID_TIER, server_default="paid_tier", nullable=False
    )
    policy_config: Mapped[dict] = mapped_column(
        JSONB, default=dict, server_default=text("'{}'::jsonb"), nullable=False
    )
    owner_email: Mapped[str | None] = mapped_column(String(320))
    signup_ip: Mapped[str | None] = mapped_column(String(64))


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, server_default=text("gen_random_uuid()")
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id"), nullable=False, index=True
    )
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    name: Mapped[str | None] = mapped_column(String(200))
    role: Mapped[UserRole] = mapped_column(
        _enum(UserRole), default=UserRole.AGENT, server_default="agent", nullable=False
    )

    __table_args__ = (Index("uq_users_tenant_email", "tenant_id", "email", unique=True),)


class ApiKey(Base, TimestampMixin):
    __tablename__ = "api_keys"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, server_default=text("gen_random_uuid()")
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    key_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    rate_limit_tier: Mapped[str] = mapped_column(
        String(32), server_default="standard", nullable=False
    )
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class KnowledgeSource(Base, TimestampMixin):
    __tablename__ = "knowledge_sources"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, server_default=text("gen_random_uuid()")
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id"), nullable=False, index=True
    )
    kind: Mapped[SourceKind] = mapped_column(_enum(SourceKind), nullable=False)
    origin_url: Mapped[str | None] = mapped_column(String(2048))
    title: Mapped[str | None] = mapped_column(String(500))
    version: Mapped[int] = mapped_column(Integer, server_default=text("1"), nullable=False)
    status: Mapped[SourceStatus] = mapped_column(
        _enum(SourceStatus), default=SourceStatus.PENDING, server_default="pending", nullable=False
    )
    content_hash: Mapped[str | None] = mapped_column(String(64))
    error: Mapped[str | None] = mapped_column(Text)


class Chunk(Base, TimestampMixin):
    __tablename__ = "chunks"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, server_default=text("gen_random_uuid()")
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id"), nullable=False, index=True
    )
    source_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("knowledge_sources.id"), nullable=False, index=True
    )
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_tsv: Mapped[str | None] = mapped_column(
        TSVECTOR, Computed("to_tsvector('english', content)", persisted=True)
    )
    # 768-dim: production embedding API (text-embedding-004 class); nullable until embedded
    embedding: Mapped[list[float] | None] = mapped_column(Vector(768))
    token_count: Mapped[int | None] = mapped_column(Integer)

    __table_args__ = (
        Index(
            "ix_chunks_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
        Index("ix_chunks_tsv_gin", "content_tsv", postgresql_using="gin"),
        Index("uq_chunks_source_ordinal", "source_id", "ordinal", unique=True),
    )


class Ticket(Base, TimestampMixin):
    __tablename__ = "tickets"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, server_default=text("gen_random_uuid()")
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id"), nullable=False, index=True
    )
    external_ref: Mapped[str | None] = mapped_column(String(200))
    subject: Mapped[str] = mapped_column(String(500), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[TicketStatus] = mapped_column(
        _enum(TicketStatus), default=TicketStatus.NEW, server_default="new", nullable=False
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id"))


class Analysis(Base, TimestampMixin):
    """The audit trail (ADR-005) — every analysis persisted before response."""

    __tablename__ = "analyses"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, server_default=text("gen_random_uuid()")
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id"), nullable=False, index=True
    )
    ticket_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("tickets.id"), nullable=False, index=True
    )
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    severity: Mapped[str] = mapped_column(String(8), nullable=False)
    difficulty: Mapped[str] = mapped_column(String(16), nullable=False)
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    answer: Mapped[str | None] = mapped_column(Text)
    policy_flags: Mapped[list] = mapped_column(
        JSONB, default=list, server_default=text("'[]'::jsonb"), nullable=False
    )
    citations: Mapped[list] = mapped_column(
        JSONB, default=list, server_default=text("'[]'::jsonb"), nullable=False
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id"))
    confidence: Mapped[float | None] = mapped_column(Float)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    prompt_tokens: Mapped[int | None] = mapped_column(Integer)
    completion_tokens: Mapped[int | None] = mapped_column(Integer)
    cost_usd: Mapped[float | None] = mapped_column(Numeric(12, 8))
    provider: Mapped[str | None] = mapped_column(String(50))
    model: Mapped[str | None] = mapped_column(String(80))
    prompt_version: Mapped[str | None] = mapped_column(String(40))


class Conversation(Base, TimestampMixin):
    __tablename__ = "conversations"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, server_default=text("gen_random_uuid()")
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id"), nullable=False, index=True
    )
    ticket_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("tickets.id"), index=True)
    title: Mapped[str | None] = mapped_column(String(300))


class Message(Base, TimestampMixin):
    __tablename__ = "messages"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, server_default=text("gen_random_uuid()")
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("conversations.id"), nullable=False, index=True
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id"), nullable=False, index=True
    )
    role: Mapped[MessageRole] = mapped_column(_enum(MessageRole), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)


class UsageEvent(Base, TimestampMixin):
    __tablename__ = "usage_events"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, server_default=text("gen_random_uuid()")
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id"), nullable=False, index=True
    )
    kind: Mapped[str] = mapped_column(String(40), nullable=False)  # classify | draft | embed | ...
    provider: Mapped[str | None] = mapped_column(String(50))
    model: Mapped[str | None] = mapped_column(String(80))
    prompt_tokens: Mapped[int | None] = mapped_column(Integer)
    completion_tokens: Mapped[int | None] = mapped_column(Integer)
    cost_usd: Mapped[float | None] = mapped_column(Numeric(12, 8))
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    request_id: Mapped[str | None] = mapped_column(String(64))
    event_metadata: Mapped[dict] = mapped_column(
        "metadata", JSONB, default=dict, server_default=text("'{}'::jsonb"), nullable=False
    )

"""/v1/tickets — create + analyze (P2), list, and the audit trail.

Cross-tenant reads are impossible by construction: every query runs inside
the caller's RLS binding, so a ticket_id from another tenant is simply
invisible (empty result), not a leak.
"""

import uuid

import structlog
from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.domain import AnalysisResponse, TicketCreate
from app.models import Analysis, Tenant, Ticket
from app.security import require_tenant

router = APIRouter(prefix="/v1/tickets", tags=["tickets"])


@router.post("", status_code=201, response_model=AnalysisResponse)
async def create_ticket(
    payload: TicketCreate,
    request: Request,
    tenant: Tenant = Depends(require_tenant),
    session: AsyncSession = Depends(get_session),
) -> AnalysisResponse:
    documents: dict[str, str] = {}
    retriever = getattr(request.app.state, "retriever", None)
    if retriever is not None:
        try:
            docs = await retriever.retrieve(
                session,
                query=f"{payload.subject}\n{payload.body}",
                k=3,
            )
            documents = {d["citation"]: d["content"] for d in docs}
        except Exception as exc:  # noqa: BLE001 - missing knowledge must not block analysis
            structlog.get_logger(__name__).warning("retrieval_failed", error=str(exc)[:200])

    return await request.app.state.analyzer.analyze(
        session,
        tenant,
        subject=payload.subject,
        body=payload.body,
        request_id=request.headers.get("x-request-id"),
        documents=documents,
    )


@router.get("")
async def list_tickets(
    tenant: Tenant = Depends(require_tenant),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    rows = (
        (await session.execute(select(Ticket).order_by(Ticket.created_at.desc()).limit(50)))
        .scalars()
        .all()
    )
    return [
        {
            "id": str(t.id),
            "subject": t.subject,
            "status": t.status.value,
            "created_at": t.created_at.isoformat(),
        }
        for t in rows
    ]


@router.get("/{ticket_id}/analyses")
async def ticket_analyses(
    ticket_id: uuid.UUID,
    tenant: Tenant = Depends(require_tenant),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    rows = (
        (
            await session.execute(
                select(Analysis)
                .where(Analysis.ticket_id == ticket_id)
                .order_by(Analysis.created_at.asc())
            )
        )
        .scalars()
        .all()
    )
    return [
        {
            "id": str(a.id),
            "action": a.action,
            "category": a.category,
            "answer": a.answer,
            "policy_flags": a.policy_flags,
            "confidence": a.confidence,
            "latency_ms": a.latency_ms,
            "provider": a.provider,
            "model": a.model,
            "created_at": a.created_at.isoformat(),
        }
        for a in rows
    ]

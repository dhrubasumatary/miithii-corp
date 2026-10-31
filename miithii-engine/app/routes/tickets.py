"""/v1/tickets — create + analyze (P2), list, and the audit trail.

Cross-tenant reads are impossible by construction: every query runs inside
the caller's RLS binding, so a ticket_id from another tenant is simply
invisible (empty result), not a leak.
"""

import asyncio
import json
import uuid

import structlog
from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
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


@router.post("/stream")
async def create_ticket_stream(
    payload: TicketCreate,
    request: Request,
    tenant: Tenant = Depends(require_tenant),
    session: AsyncSession = Depends(get_session),
) -> StreamingResponse:
    """SSE: real pipeline stages (classify -> retrieve -> policy -> draft) + result."""

    async def generate():
        def sse(event: str, data: dict) -> str:
            return f"event: {event}\ndata: {json.dumps(data)}\n\n"

        try:
            yield sse("progress", {"stage": "classify"})

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
                except Exception as exc:  # noqa: BLE001
                    structlog.get_logger(__name__).warning("retrieval_failed", error=str(exc)[:200])
            yield sse("progress", {"stage": "retrieve"})

            queue: asyncio.Queue = asyncio.Queue()
            task = asyncio.create_task(
                request.app.state.analyzer.analyze(
                    session,
                    tenant,
                    subject=payload.subject,
                    body=payload.body,
                    request_id=request.headers.get("x-request-id"),
                    documents=documents,
                    progress=queue.put_nowait,
                )
            )
            while True:
                getter = asyncio.create_task(queue.get())
                done, _ = await asyncio.wait(
                    {task, getter}, return_when=asyncio.FIRST_COMPLETED
                )
                if getter in done:
                    yield sse("progress", {"stage": getter.result()})
                if task in done:
                    result = task.result()
                    break

            yield sse("result", result.model_dump())
        except Exception as exc:  # noqa: BLE001 - stream the failure, never hang
            yield sse("error", {"detail": str(exc)[:300]})

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
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

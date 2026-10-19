"""HTTP compatibility endpoint backed by the shared guardrail pipeline."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.app.guardrails.pipeline import GuardrailPipeline, PipelineStatus
from backend.app.integrations.models import ConnectionCategory
from backend.app.integrations.store import connection_store
from backend.app.observability.traces import TraceEvent, TraceRecord, trace_store


class DocumentInput(BaseModel):
    content: str


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=100_000)
    documents: list[DocumentInput] = Field(default_factory=list)
    proposed_actions: list[dict[str, Any]] = Field(default_factory=list)
    ai_connection_id: UUID | None = None
    data_connection_ids: list[UUID] = Field(default_factory=list, max_length=20)


router = APIRouter(tags=["guardrails"])
pipeline = GuardrailPipeline()


@router.post("/chat")
async def chat_endpoint(request: ChatRequest) -> dict[str, Any]:
    started_at = datetime.now(timezone.utc)
    trace_id = uuid4()

    if request.ai_connection_id is not None:
        ai_connection = connection_store.get(request.ai_connection_id)
        if ai_connection is None or ai_connection.category is not ConnectionCategory.AI_PROVIDER:
            raise HTTPException(status_code=404, detail="AI connection not found.")
    for connection_id in request.data_connection_ids:
        data_connection = connection_store.get(connection_id)
        if data_connection is None or data_connection.category is ConnectionCategory.AI_PROVIDER:
            raise HTTPException(status_code=404, detail="Data connection not found.")

    decision = pipeline.inspect_before_agent(
        message=request.message,
        documents=[document.content for document in request.documents],
        proposed_actions=request.proposed_actions,
    )

    if decision.status is PipelineStatus.BLOCKED:
        raw_response = "Request blocked by Guard-AI policy."
    elif decision.status is PipelineStatus.NEEDS_APPROVAL:
        raw_response = "The proposed action requires approval and was not executed."
    else:
        # This endpoint proves the security boundary without introducing an
        # external model or tool side effect.
        raw_response = f"Guard-AI accepted: {request.message}"

    output_result = pipeline.inspect_output(raw_response)
    response = output_result.transformed_content or raw_response
    results = (*decision.results, output_result)

    trace_store.add(
        TraceRecord(
            trace_id=trace_id,
            started_at=started_at,
            completed_at=datetime.now(timezone.utc),
            status=decision.status.value,
            ai_connection_id=request.ai_connection_id,
            data_connection_ids=request.data_connection_ids,
            events=[
                TraceEvent(
                    stage=result.category,
                    guardrail=result.guardrail,
                    status=result.action.value,
                    severity=result.severity.value,
                    detail=result.reason,
                    matched_rules=list(result.matched_rules),
                    metadata=dict(result.metadata),
                )
                for result in results
            ],
        )
    )

    return {
        "trace_id": str(trace_id),
        "status": decision.status.value,
        "response": response,
        "sanitized_documents": list(decision.sanitized_documents),
        "guardrails": [result.to_dict() for result in results],
        "connections": {
            "ai": str(request.ai_connection_id) if request.ai_connection_id else None,
            "data": [str(connection_id) for connection_id in request.data_connection_ids],
        },
    }

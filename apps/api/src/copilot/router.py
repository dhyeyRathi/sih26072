"""REST endpoints for the deterministic meteorological copilot."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .rag import answer_question, get_suggestions


router = APIRouter(prefix="/copilot", tags=["copilot"])


class CopilotChatRequest(BaseModel):
    """A bounded request body for a source-grounded copilot response."""

    question: str = Field(..., min_length=1, max_length=1200)
    cell_id: Optional[str] = Field(default=None, max_length=64)
    include_live_data: bool = True
    document_limit: int = Field(default=3, ge=1, le=4)


@router.post("/chat")
async def copilot_chat(request: CopilotChatRequest):
    """Answer a forecaster question with sources and inspectable tool payloads."""
    try:
        return answer_question(
            request.question,
            cell_id=request.cell_id,
            include_live_data=request.include_live_data,
            document_limit=request.document_limit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/suggestions")
async def copilot_suggestions():
    """Provide stable, frontend-ready examples without calling live services."""
    suggestions = get_suggestions()
    return {"count": len(suggestions), "suggestions": suggestions}


__all__ = ["CopilotChatRequest", "router"]

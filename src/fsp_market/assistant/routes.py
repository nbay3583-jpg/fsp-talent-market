"""Public helper endpoints (no AI API): fixed knowledge base, deterministic answers."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field

from fsp_market.assistant import service

router = APIRouter(prefix="/api/assistant", tags=["assistant"])


class AskIn(BaseModel):
    question: str = Field(min_length=2, max_length=300)
    role: Literal["candidate", "employer"] | None = None


@router.post("/ask")
def ask(body: AskIn) -> dict:
    return service.ask(body.question, body.role)


@router.get("/suggestions")
def suggestions(role: Literal["candidate", "employer"] | None = None) -> dict:
    return {"suggestions": service.suggestions(role)}

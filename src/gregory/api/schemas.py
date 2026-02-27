"""Pydantic schemas for API."""

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """Request body for POST /users/{user_id}/chat."""

    message: str = Field(..., min_length=1, max_length=16_384)


class ChatResponse(BaseModel):
    """Response for POST /users/{user_id}/chat."""

    response: str
    conversation_id: str


class UsersResponse(BaseModel):
    """Response for GET /users."""

    users: list[str]


class HealthResponse(BaseModel):
    """Response for GET /health."""

    status: str = "ok"
    ollama_configured: bool = False
    ai_provider: str | None = None

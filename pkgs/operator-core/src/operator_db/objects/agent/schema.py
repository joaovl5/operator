"""Session-agent service schemas."""

from datetime import datetime  # noqa: TC003
from typing import ClassVar

from pydantic import BaseModel, ConfigDict


class AgentSchema(BaseModel):
    """Shared session-agent fields."""

    model_config: ClassVar[ConfigDict] = ConfigDict(from_attributes=True)

    local_id: str
    model: str | None = None
    system_prompt: str | None = None
    serialized_permissions: dict[str, object] | None = None
    title: str | None = None
    description: str | None = None
    extra_detail: str | None = None


class AgentRequestSchema(AgentSchema):
    """Session-agent create payload."""

    session_id: str


class AgentResponseSchema(AgentSchema):
    """Persisted session-agent payload."""

    id: str
    session_id: str
    history_id: str
    created_at: datetime
    updated_at: datetime


__all__ = [
    "AgentRequestSchema",
    "AgentResponseSchema",
    "AgentSchema",
]

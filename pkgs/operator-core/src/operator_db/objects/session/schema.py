"""Session service schemas."""

from datetime import datetime
from typing import ClassVar

from pydantic import BaseModel, ConfigDict


class SessionSchema(BaseModel):
    """Shared session fields."""

    model_config: ClassVar[ConfigDict] = ConfigDict(from_attributes=True)

    title: str | None = None
    description: str | None = None
    extra_detail: str | None = None


class SessionRequestSchema(SessionSchema):
    """Session create/update payload."""


class SessionResponseSchema(SessionSchema):
    """Persisted session payload."""

    id: str
    created_at: datetime
    updated_at: datetime


__all__ = [
    "SessionRequestSchema",
    "SessionResponseSchema",
    "SessionSchema",
]

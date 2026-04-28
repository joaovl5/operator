"""History service schemas."""

from datetime import datetime  # noqa: TC003
from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field

from operator_db.constants.role import HistoryMessageRole  # noqa: TC001

JsonPayload = dict[str, object] | list[object] | str | int | float | bool | None


class HistorySchema(BaseModel):
    """Shared history fields."""

    model_config: ClassVar[ConfigDict] = ConfigDict(from_attributes=True)

    title: str | None = None
    description: str | None = None
    extra_detail: str | None = None


class HistoryRequestSchema(HistorySchema):
    """History create/update payload."""


class HistoryResponseSchema(HistorySchema):
    """Persisted history payload."""

    id: str
    created_at: datetime
    updated_at: datetime


class HistoryEpochSchema(BaseModel):
    """Shared history epoch fields."""

    model_config: ClassVar[ConfigDict] = ConfigDict(from_attributes=True)

    title: str | None = None
    description: str | None = None
    extra_detail: str | None = None


class HistoryEpochRequestSchema(HistoryEpochSchema):
    """History epoch create payload."""


class HistoryEpochResponseSchema(HistoryEpochSchema):
    """Persisted history epoch payload."""

    id: str
    history_id: str
    epoch_iteration: int
    created_at: datetime
    updated_at: datetime


class HistoryMessageSchema(BaseModel):
    """Shared history message fields."""

    model_config: ClassVar[ConfigDict] = ConfigDict(from_attributes=True)

    role: HistoryMessageRole
    author_id: str | None = None
    text_contents: str | None = None
    binary_contents: bytes | None = None
    json_contents: JsonPayload = None
    extra_metadata: dict[str, object] = Field(default_factory=dict)


class HistoryMessageRequestSchema(HistoryMessageSchema):
    """History message append payload."""


class HistoryMessageResponseSchema(HistoryMessageSchema):
    """Persisted history message payload."""

    id: str
    epoch_id: str
    message_index: int
    compacted_by_id: str | None = None
    created_at: datetime
    updated_at: datetime


__all__ = [
    "HistoryEpochRequestSchema",
    "HistoryEpochResponseSchema",
    "HistoryEpochSchema",
    "HistoryMessageRequestSchema",
    "HistoryMessageResponseSchema",
    "HistoryMessageSchema",
    "HistoryRequestSchema",
    "HistoryResponseSchema",
    "HistorySchema",
    "JsonPayload",
]

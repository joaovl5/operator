"""Mail service schemas."""

from datetime import datetime  # noqa: TC003
from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field

from operator_db.constants.mail import MailMessageState  # noqa: TC001


class MailSchema(BaseModel):
    """Shared mail message fields."""

    model_config: ClassVar[ConfigDict] = ConfigDict(from_attributes=True)

    title: str | None = None
    body: str
    extra_metadata: dict[str, object] = Field(default_factory=dict)


class MailRequestSchema(MailSchema):
    """Mail queue payload."""

    session_id: str
    sender_local_ids: list[str]
    receiver_local_ids: list[str]


class MailDeliveryResponseSchema(BaseModel):
    """Persisted mail delivery payload."""

    model_config: ClassVar[ConfigDict] = ConfigDict(from_attributes=True)

    mail_message_id: str
    sender_agent_id: str
    receiver_agent_id: str
    sender_local_id: str
    receiver_local_id: str
    state: MailMessageState


class MailResponseSchema(MailSchema):
    """Persisted mail message payload."""

    id: str
    created_at: datetime
    updated_at: datetime
    deliveries: list[MailDeliveryResponseSchema] = Field(default_factory=list)


__all__ = [
    "MailDeliveryResponseSchema",
    "MailRequestSchema",
    "MailResponseSchema",
    "MailSchema",
]

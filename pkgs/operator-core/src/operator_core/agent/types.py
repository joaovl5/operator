"""Runtime-local agent type aliases and models."""

from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from operator_core.mail.mail import (
    DEFAULT_USER_RECIPIENT_ID,
    MailMessage,
    MailMessageContents,
    MailRecipient,
    RecipientType,
)
from operator_shared.time.utils import mk_time

if TYPE_CHECKING:
    from datetime import datetime

ORCHESTRATOR_ID = "orchestrator"


class UserMessage(BaseModel):
    """Message object for direct communication to an agent."""

    contents: str
    target_agent_id: str = Field(ORCHESTRATOR_ID)
    source_user_id: str = Field(DEFAULT_USER_RECIPIENT_ID)
    sent_at: datetime = Field(default_factory=mk_time)

    def to_mail_message(self) -> MailMessage:
        """Convert this user-given message into the more generic `MailMessage` type."""
        return MailMessage(
            sent_from=MailRecipient(
                id=self.source_user_id,
                type=RecipientType.USER,
            ),
            sent_to=[MailRecipient(id=self.target_agent_id, type=RecipientType.AGENT)],
            contents=MailMessageContents(
                title=None,
                body=self.contents,
                metadata={},
            ),
        )

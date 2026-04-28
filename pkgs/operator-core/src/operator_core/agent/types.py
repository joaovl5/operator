"""Runtime-local agent type aliases and models."""

import datetime as dt

from pydantic import BaseModel, Field

from operator_core.mail.mail import (
    DEFAULT_USER_RECIPIENT_ID,
    MailMessage,
    MailMessageContents,
    MailRecipient,
    RecipientType,
)
from operator_shared.time.utils import mk_time

ORCHESTRATOR_ID = "orchestrator"


class UserMessage(BaseModel):
    """Message object for direct communication to an agent."""

    contents: str
    target_agent_id: str = Field(default=ORCHESTRATOR_ID)
    source_user_id: str = Field(default=DEFAULT_USER_RECIPIENT_ID)
    sent_at: dt.datetime = Field(default_factory=mk_time)

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

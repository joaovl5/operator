import datetime as dt
from enum import StrEnum

from pydantic import BaseModel, Field

from operator_shared.time.utils import mk_time

DEFAULT_USER_RECIPIENT_ID = "user"


# turn into adt later
class RecipientType(StrEnum):
    AGENT = "agent"
    USER = "user"


class MailRecipient(BaseModel):
    id: str
    type: RecipientType


class MailMessageContents(BaseModel):
    title: str | None = None
    body: str | None = None
    metadata: dict[str, object] = Field(default_factory=dict)


class MailMessage(BaseModel):
    sent_from: MailRecipient
    sent_to: list[MailRecipient]
    sent_at: dt.datetime = Field(default_factory=mk_time)

    contents: MailMessageContents


class RenderedMailMessage(BaseModel):
    """Mail message from some perspective."""

    author: MailRecipient
    time: dt.datetime
    contents: MailMessageContents


class Mailbox(BaseModel):
    """Group of messages from A to B."""

    messages: list[MailMessage]

    def add(self, msg: MailMessage) -> None:
        """Add a message to the mailbox."""
        self.messages.append(msg)

    def render(
        self,
        *,
        receiver_id: str,
        reverse_order: bool = False,
    ) -> list[RenderedMailMessage]:
        """Renders messages from perspective of `receiver_id`."""
        rendered_msgs: list[RenderedMailMessage] = []

        for msg in self.messages:
            target_ids = [x.id for x in msg.sent_to]
            should_add = msg.sent_from.id == receiver_id or receiver_id in target_ids
            if should_add:
                rendered_msgs.append(
                    RenderedMailMessage(
                        author=msg.sent_from,
                        time=msg.sent_at,
                        contents=msg.contents,
                    ),
                )

        rendered_msgs.sort(
            key=lambda x: x.time,
            reverse=reverse_order,
        )

        return rendered_msgs

from enum import StrEnum
from typing import Annotated, Literal

from advanced_alchemy.types import JsonB
from pydantic import BaseModel, Discriminator, JsonValue
from sqlalchemy import Text
from sqlalchemy.orm import mapped_column

type OptStr = Annotated[
    str | None,
    mapped_column(
        default=None,
        nullable=True,
    ),
]

type OptText = Annotated[
    str | None,
    mapped_column(
        Text,
        default=None,
        nullable=True,
    ),
]

type OptJson = Annotated[
    JsonValue | None,
    mapped_column(
        JsonB,
        default=None,
        nullable=True,
    ),
]


class MsgRole(StrEnum):
    """Role of author in a message."""

    SYSTEM = "system"
    """System-related message, directly by harness.

    Can be system prompt, info unrelated to tool execution, and so on.
    """

    USER = "user"
    """Message by user, when convo is directly with user."""

    AGENT_OTHER = "agent_other"
    """Message by other agent, when convo. is with another agent."""

    AGENT_SELF = "agent_self"
    """Message by self (current agent.)

    Text/content parts only.
    """

    AGENT_SELF_THINKING = "agent_self_thinking"
    """Thinking-part of agent response."""

    TOOL_CALL = "tool_call"
    """Tool call by self."""

    TOOL_REPLY = "tool_reply"
    """Tool call response."""

    TOOL_RETRY = "tool_try"
    """Tool call failure response."""

    FILE_SELF = "file_self"
    """File sent from self (agent response.)"""

    FILE_OTHER = "file_other"
    """File sent from other party (user/agent.)"""


class ForkReconcileValue:
    class _Base(BaseModel): ...

    class Omit(_Base):
        """Omit fork info and continue as if it didn't happen."""

        kind: Literal["omit"]

    class Merge(_Base):
        """Merge entire fork's events."""

        kind: Literal["merge"]

    class Summary(_Base):
        """Use a generated summary to brief into forked delta."""

        kind: Literal["summary"]

        contents: str

    type _IsReconcile[T: _Base] = T
    type Type = _IsReconcile[
        Annotated[
            Omit  # .
            | Merge
            | Summary,
            Discriminator("kind"),
        ]
    ]


class ForkReconcile(BaseModel):
    """Methods of reconciling a forked branch."""

    value: ForkReconcileValue.Type


class SettingsPayload(BaseModel):
    """Payload for settings event."""

    model_name: str
    model_provider: str

    permissions: JsonValue

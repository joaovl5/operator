from enum import StrEnum

from pydantic import BaseModel, JsonValue


class StopAgentMethod(StrEnum):
    KILL = "kill"
    """Don't wait for anything and just abort any agent-related tasks."""

    WAIT_LOOP = "wait-loop"
    """Stop after agent's loop is done."""

    WAIT_TURN = "wait-turn"
    """Stop after agent's loop turn is done."""


class IncomingMessage(BaseModel):
    """Message object for communication to/from agent/user."""

    text_data: str | None = None
    json_data: JsonValue | None = None
    bytes_data: bytes | None = None

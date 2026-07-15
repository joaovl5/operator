from typing import TYPE_CHECKING, Annotated, Literal

from attrs import define
from pydantic import BaseModel, Discriminator
from pydantic_ai import Agent, ToolOutput

if TYPE_CHECKING:
  from sqlalchemy.ext.asyncio import AsyncSession

  from operator_db.objects import SessionAgent
  from operator_shared.settings import OperatorSettings


@define
class ToolDeps:
  """Dependency-injected things for tool calls to use."""

  settings: OperatorSettings
  db_session: AsyncSession
  db_obj: SessionAgent


class ChatOut(BaseModel):
  """Send message to user."""

  kind: Literal["chat"] = "chat"

  message: str


class AskOut(BaseModel):
  """Ask user for clarification."""

  kind: Literal["ask"] = "ask"

  question: str


type AgentOutput = Annotated[
  ChatOut | AskOut,
  Discriminator("kind"),
]
type AgentType = Agent[ToolDeps, AgentOutput]


def construct_out_type() -> list[ToolOutput[AgentOutput]]:
  """Gets properly created `ToolOutput` list."""
  return [
    ToolOutput(ChatOut, name="chat"),
    ToolOutput(AskOut, name="ask"),
  ]

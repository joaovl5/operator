from typing import TYPE_CHECKING

from attrs import define
from pydantic_ai import Agent

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


type AgentType = Agent[ToolDeps, str]

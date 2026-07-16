from typing import TYPE_CHECKING, override

from attrs import define
from pydantic import Field

from operator_core_olden.agent.main import OpAgent, PermissionGroup
from operator_core_olden.providers.factory import (
  build_model_from_config,
)
from operator_core_olden.toolsets.base import (
  BaseToolset,
  ToolsetPydanticExport,
)
from operator_db.objects import HistoryMessageResponseSchema
from operator_shared.forms import BaseForm

if TYPE_CHECKING:
  from collections.abc import Callable

  from pydantic_ai.models import Model

  from operator_core_olden.config import OperatorConfig
  from operator_core_olden.session.session import Session


class SpawnSubagentRequest(BaseForm):
  agent_id: str = Field(
    description="ID for subagent - must be unique session-wide",
  )
  prompt: str = Field(
    description="Instructions and any info to be given to subagent"
  )


class SpawnSubagentError(BaseForm):
  message: str = Field(description="Error message")


class SpawnSubagentSuccess(BaseForm):
  agent_response: str = Field(description="Response from the agent")


type SpawnSubagentResponse = SpawnSubagentError | SpawnSubagentSuccess


@define
class SubagentToolset(BaseToolset):
  session: Session

  @override
  def export_to_pydantic(self) -> ToolsetPydanticExport:
    return [
      self.spawn_subagent,
    ]

  @staticmethod
  def _mk_model_default(cfg: OperatorConfig) -> Model:
    return build_model_from_config(
      config=cfg.model,
    )

  @staticmethod
  def _mk_prompt_default(cfg: OperatorConfig) -> str:
    txt = cfg.agent.system_prompt.strip()
    if txt:
      return "You're a helpful assistant."
    return txt

  def _mk_agent(
    self,
    *,
    model_builder_function: Callable[[OperatorConfig], Model]
    | None = None,
    prompt_assembler_function: Callable[[OperatorConfig], str]
    | None = None,
    history_id: str | None = None,
    perms: PermissionGroup | None = None,
    agent_id: str,
  ) -> OpAgent:
    model_builder_function = (
      model_builder_function or self._mk_model_default
    )
    prompt_assembler_function = (
      prompt_assembler_function or self._mk_prompt_default
    )
    perms = perms or self.session.orchestrator.permissions

    return OpAgent(
      id=agent_id,
      model=model_builder_function(self.session.config),
      system_prompt=prompt_assembler_function(self.session.config),
      permissions=perms,
      history_id=history_id,
    )

  async def subagent_reply(self, msg: str) -> None:
    """Give final reply for initial query."""

  async def spawn_subagent(
    self, req: SpawnSubagentRequest
  ) -> SpawnSubagentResponse:
    """Spawn an ephemeral subagent in foreground, return its response on a query."""
    if req.agent_id in self.session.agents:
      return SpawnSubagentError(
        message="Subagent with that name already exists.",
      )
    ag = self._mk_agent(agent_id=req.agent_id)
    ag.register_toolsets([self.subagent_reply])

    while True:
      # FIXME: EVERYTHING IS ATROCIOUS AND NEEDS TO BE DESTROYED
      msgs: list[HistoryMessageResponseSchema] = []
      await ag.run(messages=msgs)

    return SpawnSubagentSuccess()

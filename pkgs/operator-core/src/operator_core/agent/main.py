from importlib import import_module
from typing import TYPE_CHECKING

from attrs import define, field
from pydantic import BaseModel
from pydantic_ai import Agent

if TYPE_CHECKING:
    from operator_core.providers import ModelProvider
else:
    ModelProvider = import_module("operator_core.providers").ModelProvider


@define(kw_only=True)
class OperatorAgent[
    OutType: BaseModel,
    ConfigT: BaseModel,
]:
    """Operator agent instance."""

    provider: ModelProvider[ConfigT]
    output_type: type[OutType]
    model_config: ConfigT
    agent: Agent[None, OutType] = field(init=False)

    def __attrs_post_init__(self) -> None:
        """Initialize internal pydantic-ai agent."""
        self.agent = Agent(
            model=self.provider.build_model(model_config=self.model_config),
            output_type=self.output_type,
        )

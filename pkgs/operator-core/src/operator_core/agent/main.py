from asyncio import Lock
from typing import TYPE_CHECKING

from attrs import Factory, define, field
from pydantic_ai import Agent

if TYPE_CHECKING:
    from pydantic_ai.models import Model


@define(kw_only=True)
class OpAgent:
    """Simple agent for testing."""

    model: Model
    lock: Lock = Factory(Lock)
    agent: Agent = field(init=False)

    def __attrs_post_init__(self) -> None:
        """Initialize internal pydantic-ai agent."""
        self.agent = Agent(
            model=self.model,
        )

"""Runtime-local agent type aliases and models."""

from datetime import datetime

from pydantic import BaseModel, Field

from operator_shared.time.utils import mk_time

ORCHESTRATOR_ID = "orchestrator"
USER_ID = "user"


class UserMessage(BaseModel):
  """Message object for direct communication to an agent."""

  contents: str
  target_agent_id: str = Field(default=ORCHESTRATOR_ID)
  source_user_id: str = Field(default=USER_ID)
  sent_at: datetime = Field(default_factory=mk_time)

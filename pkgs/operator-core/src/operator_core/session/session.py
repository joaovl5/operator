from typing import TYPE_CHECKING

from attrs import Factory, define

from operator_core.agent.types import ORCHESTRATOR_KEY, UserMessage
from operator_shared.time.utils import mk_time

if TYPE_CHECKING:
    from datetime import datetime, timedelta

    from operator_core.agent.main import OpAgent
    from operator_core.mail.mail import Mailbox


def get_orchestrator_agent() -> OpAgent:  # pyright: ignore[reportReturnType]
    """Create Orchestrator `OpAgent`."""


@define(kw_only=True)
class Session:
    agents: dict[str, OpAgent] = Factory(dict)  # pyright: ignore[reportUnknownVariableType]
    mailbox: Mailbox

    time_start: datetime = Factory(mk_time)

    def __attrs_post_init__(self) -> None:
        """Initialize agents, if necessary."""
        if ORCHESTRATOR_KEY not in self.agents:
            self.agents[ORCHESTRATOR_KEY] = get_orchestrator_agent()

    @property
    def time_elapsed(self) -> timedelta:
        """Returns elapsed time from `time_start`."""
        time_now = mk_time()
        return time_now - self.time_start

    async def send_user_message(self, msg: UserMessage):
        """Send an user-sourced message to an agent."""
        self.mailbox.add(
            msg=msg.to_mail_message(),
        )

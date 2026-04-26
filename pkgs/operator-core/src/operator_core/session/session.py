from typing import TYPE_CHECKING

from anyio import Path
from attrs import Factory, define

from operator_core.agent.main import OpAgent, PermissionGroup
from operator_core.agent.types import ORCHESTRATOR_ID, UserMessage
from operator_core.permissions import (
    FilesystemScope,
    Permission,
    PermissionType,
    TemporalScope,
)
from operator_core.session.errors import SessionMissingAgentError
from operator_shared.time.utils import mk_time

if TYPE_CHECKING:
    from datetime import datetime, timedelta

    from operator_core.mail.mail import Mailbox


def get_orchestrator_perms() -> PermissionGroup:
    """Gather perms for Orchestrator."""
    cwd_stub = Path(".")
    fs_scope = FilesystemScope(path=cwd_stub)
    t_scope = TemporalScope.All()
    perms: list[PermissionType] = [
        Permission.Filesystem.Read(scope=fs_scope),
        Permission.Filesystem.Edit(scope=fs_scope),
        Permission.Subagent(),
    ]
    return PermissionGroup(
        perms=[t_scope.wrap_permission(perm) for perm in perms],
    )


def get_orchestrator_agent() -> OpAgent:
    """Create Orchestrator `OpAgent`."""
    return OpAgent(
        model=...,  # pyright: ignore[reportArgumentType]
        permissions=get_orchestrator_perms(),
    )


@define(kw_only=True)
class Session:
    agents: dict[str, OpAgent] = Factory(dict)  # pyright: ignore[reportUnknownVariableType]
    mailbox: Mailbox

    time_start: datetime = Factory(mk_time)

    def __attrs_post_init__(self) -> None:
        """Initialize agents, if necessary."""
        if ORCHESTRATOR_ID not in self.agents:
            self.agents[ORCHESTRATOR_ID] = get_orchestrator_agent()

    @property
    def time_elapsed(self) -> timedelta:
        """Returns elapsed time from `time_start`."""
        time_now = mk_time()
        return time_now - self.time_start

    async def send_user_message(self, msg: UserMessage) -> None:
        """Send an user-sourced message to an agent, prompting/queue-ing agent's turn."""
        self.mailbox.add(
            msg=msg.to_mail_message(),
        )

    async def agent_turn(self, agent_id: str) -> None:
        """Acquire agent for running a single step."""
        agent = self.agents.get(agent_id)
        if agent is None:
            raise SessionMissingAgentError
        async with agent.lock:
            pass

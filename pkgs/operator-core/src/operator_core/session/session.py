from typing import TYPE_CHECKING

from anyio import Path
from attrs import Factory, define

from operator_core.agent.main import OpAgent
from operator_core.agent.types import ORCHESTRATOR_ID, UserMessage
from operator_core.permissions import (
    FilesystemScope,
    Permission,
    PermissionGroup,
    PermissionType,
    TemporalScope,
)
from operator_core.session.errors import SessionAgentUnavailableError, SessionMissingAgentError
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
        id=ORCHESTRATOR_ID,
        model=...,  # pyright: ignore[reportArgumentType]
        system_prompt="",
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
        await self.agent_loop(agent_id=msg.target_agent_id)

    async def _verify_agent_may_run(self, _agent: OpAgent) -> None:
        """Verifies an agent can proceed to a turn. (Currently a stub).

        This is done for checking:
        - is context window near exhaustion?
        - is max turn count reached?

        In these circumstances, special exceptions are raised for handling cases:
        - context needs compaction: raise a SessionRequiresCompaction signal
        - max turn count reached: raise a SessionTurnsExhausted signal
        """

    async def agent_loop(self, agent_id: str) -> None:
        """Does agent turns (mostly) indefinitely."""
        agent = self.agents.get(agent_id)
        if agent is None:
            raise SessionMissingAgentError
        if agent.lock.locked():
            raise SessionAgentUnavailableError
        async with agent.lock:
            _agent_res = await agent.agent.run(
                message_history=[],
            )
            should_continue = True
            while should_continue:
                await self.agent_turn(agent=agent)

    async def agent_turn(self, agent: OpAgent) -> None:
        """Acquire agent for running a single step."""
        await self._verify_agent_may_run(agent)
        await agent.run()

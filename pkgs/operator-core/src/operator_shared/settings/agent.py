from pydantic import PositiveInt  # noqa: TC002

from operator_shared.settings.types import Entries, Fac, PathOrContents, SettingsBase


class _AgentSettingsBase(SettingsBase):
    prompt_core: PathOrContents | None = None
    """If set, will override core prompt for agent - aside from the obligatory harness
    base prompt."""

    prompt_append: PathOrContents | None = None
    """Value to append to the agent's prompt."""

    max_turns: PositiveInt | None = 90
    """States how many turns agent can take at most without stopping.

    If set to null, will treat the maximum as infinite.
    """


class _AgentSettingsCommon(_AgentSettingsBase): ...


class _AgentSettingsArchetype(_AgentSettingsBase):
    key: str


class AgentsSettings(SettingsBase):
    """Settings for agents.

    The hierarchy is like:
    - shared settings - defaults amongst agents
    - archetypes - specific to agent archetypes (orchestrator)
    """

    common: Fac[_AgentSettingsCommon]
    archetypes: Fac[Entries[_AgentSettingsArchetype]]

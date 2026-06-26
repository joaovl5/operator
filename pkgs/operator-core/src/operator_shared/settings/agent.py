from enum import StrEnum
from functools import cached_property
from typing import Annotated

from pydantic import Field, FilePath, PositiveInt

from operator_prompts.base import PROMPT_REGISTRY

from .types import Entries, Fac, SettingsBase
from .utils import deep_merge


class _TakesPath(SettingsBase):
    path: FilePath


class _TakesRegisteredPrompt(SettingsBase):
    prompt_key: str
    """Prompt key - will error if not found."""


type _Prompt = Annotated[
    str | _TakesPath | _TakesRegisteredPrompt,
    Field(
        description=(
            "String, or path to be read as string, or a registered prompt key. "
            "For a registered prompt key, will error if not found. Checking all"
            " registered prompts and their keys is possible via CLI."
            # TODO: LATER SHOW REGISTRY LISTINGS
        ),
    ),
]


def _read_prompt(x: _Prompt) -> str:
    """Read from a path if `x` is path."""
    match x:
        case str():
            return x
        case _TakesPath():
            return x.path.read_text()
        case _TakesRegisteredPrompt():
            if p := PROMPT_REGISTRY.get(x.prompt_key):
                return p.render()
            msg = f"Could not find prompt of key {x.prompt_key} in registry."
            raise ValueError(msg)


class _AgentSettingsBase(SettingsBase):
    prompt_core: _Prompt | None = None
    """If set, will override core prompt for agent.

    This overrides all previous prompts that are less-specific and thus isn't
    recommended for most cases - for simply appending to the prompt, use
    `prompt_append`.
    """

    prompt_append: _Prompt | None = None
    """Value to append to the agent's prompt."""

    prompt_append_extra: _Prompt | None = None
    """*Extra* value to append to the agent's prompt.

    When overriding previous settings, this won't replace the text from the base value
    of that settings' `prompt_append` value, meaning this can be used for appending
    extra contents inside an archetype override for, say, the orchestrator.
    """

    max_turns: PositiveInt | None = 90
    """States how many turns agent can take at most without stopping.

    If set to null, will treat the maximum as infinite.
    """

    permissions: Fac[dict[str, object]]
    """Placeholder value for when permissions are implemented."""


class _AgentSettingsCommon(_AgentSettingsBase): ...


class _AgentSettingsArchetype(_AgentSettingsBase):
    key: str

    use_preset_model: str | None = None
    """If set, will use that specific model preset key from `models.entries`."""


def _bake_default_common() -> _AgentSettingsCommon:
    return _AgentSettingsCommon(
        prompt_append="Agent resides in the harness Operator.",
        permissions={},
    )


class BaseArchetype(StrEnum):
    ORCHESTRATOR = "orchestrator"


def _bake_default_archetypes() -> Entries[_AgentSettingsArchetype]:
    return {
        # orchestrator shouldnt be removed
        # improve validation on this later
        BaseArchetype.ORCHESTRATOR: _AgentSettingsArchetype(
            key=BaseArchetype.ORCHESTRATOR,
            prompt_append="Agent is the orchestrator.",
            permissions={},
        ),
    }


type _PromptList = list[tuple[bool, _Prompt | None]]


class _ArchetypeOverrideBehavior(StrEnum):
    ERROR = "error"
    """Raise error if conflicts arise."""

    DEEP_MERGE = "deep_merge"
    """Deep merge definitions with the overrides taking precedence."""


class AgentsSettings(SettingsBase):
    """Settings for agents.

    The hierarchy is like:
    - shared settings - defaults amongst agents
    - archetypes - specific to agent archetypes (orchestrator)
    """

    common: _AgentSettingsCommon = Field(default_factory=_bake_default_common)
    base_archetypes: Entries[_AgentSettingsArchetype] = Field(
        default_factory=_bake_default_archetypes
    )
    """Default agent archetypes - don't edit this unless you know what you're doing."""

    extra_archetypes: Fac[Entries[_AgentSettingsArchetype]]
    """Custom archetypes to be defined.

    Keys here conflicting with base archetypes will be handled depending on the value of
    `archetype_override_behavior`.
    """

    archetype_override: _ArchetypeOverrideBehavior = _ArchetypeOverrideBehavior.ERROR
    """Controls how overriding archetypes with the `extra_archetypes` field works."""

    @cached_property
    def archetypes(self) -> Entries[_AgentSettingsArchetype]:
        """Effective computed archetypes."""
        if not self.extra_archetypes:
            return self.base_archetypes
        out = self.base_archetypes.copy()
        for k, v in self.extra_archetypes.items():
            if k not in out:
                out[k] = v
            if self.archetype_override == _ArchetypeOverrideBehavior.ERROR:
                msg = (
                    f"Conflicting extra_archetypes key `{k}` - "
                    "a base archetype already exists with this key! "
                    "If you need to override a base archetype, set "
                    "`archetype_override` to `DEEP_MERGE`."
                )
                raise ValueError(msg)
            out[k] = _AgentSettingsArchetype.model_validate(
                deep_merge(
                    self.base_archetypes[k].model_dump(),
                    v.model_dump(),
                )
            )

        return out

    def compute_effective_prompt(
        self,
        *,
        archetype: str | None = None,
        extra_cfg: _AgentSettingsCommon | None = None,
    ) -> str:
        """Compute effective prompt for an agent.

        Args:
            archetype: Which archetype is agent of, if any.
            extra_cfg: Extra overrides, if any.

        Returns:
            Computed prompt.
        """
        out: list[str] = []

        arch = self.archetypes.get(archetype) if archetype else None
        if not arch and archetype:
            msg = f"Couldn't find config for archetype {archetype}"
            raise ValueError(msg)

        prompts_common: _PromptList = [
            (True, self.common.prompt_core),
            (False, self.common.prompt_append),
            (False, self.common.prompt_append_extra),
        ]
        prompts_archetype: _PromptList = (
            [
                (True, arch.prompt_core),
                (False, arch.prompt_append),
                (False, arch.prompt_append_extra),
            ]
            if arch
            else []
        )
        prompts_extra: _PromptList = (
            [
                (True, extra_cfg.prompt_core),
                (False, extra_cfg.prompt_append),
                (False, extra_cfg.prompt_append_extra),
            ]
            if extra_cfg
            else []
        )

        for prompt_t in [
            *prompts_common,
            *prompts_archetype,
            *prompts_extra,
        ]:
            is_prompt_core, prompt = prompt_t
            if not prompt:
                continue
            content = _read_prompt(prompt)
            if is_prompt_core:
                out = [content]
                continue
            out.append(content)

        return "\n\n".join(out)

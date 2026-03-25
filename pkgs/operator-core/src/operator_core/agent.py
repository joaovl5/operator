from abc import ABC, abstractmethod
from datetime import datetime  # noqa: TC003
from typing import TYPE_CHECKING, Any, ClassVar, override

from attrs import define, field
from openai import AsyncOpenAI
from pydantic import BaseModel, ConfigDict, DirectoryPath, Field, field_validator
from pydantic_ai import Agent, ModelSettings
from pydantic_ai.models.openai import (
    OpenAIChatModel,
    OpenAIResponsesModel,
    OpenAIResponsesModelSettings,
)
from pydantic_ai.providers.openai import OpenAIProvider

from operator_core.openai_client import (
    OAuthResponsesSettings,
    OpenAIOAuthManager,
    OpenAIOAuthModelConstraintError,
    OpenAIOAuthSettingsConstraintError,
    build_chatgpt_oauth_client,
    oauth_responses_settings,
)

if TYPE_CHECKING:
    from pydantic_ai.models import Model

    from operator_core.openai_store import OpenAIOAuthStore

OPENAI_OAUTH_ALLOWED_MODELS = ("gpt-5.3-codex",)


class OpenAIModelSettings(BaseModel):
    """Serializable OpenAI model settings payload."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    openai_store: bool | None = None
    openai_send_reasoning_ids: bool | None = None
    openai_previous_response_id: str | None = None

    @classmethod
    def from_oauth_settings(cls, settings: OAuthResponsesSettings) -> OpenAIModelSettings:
        """Build model settings from OAuth-safe response defaults."""
        return cls(
            openai_store=settings.openai_store,
            openai_send_reasoning_ids=settings.openai_send_reasoning_ids,
        )


def to_model_settings(
    settings: OpenAIModelSettings, *, temperature: float
) -> OpenAIResponsesModelSettings:
    """Convert validated model settings into the pydantic-ai settings payload."""
    model_settings = OpenAIResponsesModelSettings(temperature=temperature)

    openai_store = settings.openai_store
    if openai_store is not None:
        model_settings["openai_store"] = openai_store

    openai_send_reasoning_ids = settings.openai_send_reasoning_ids
    if openai_send_reasoning_ids is not None:
        model_settings["openai_send_reasoning_ids"] = openai_send_reasoning_ids

    openai_previous_response_id = settings.openai_previous_response_id
    if openai_previous_response_id is not None:
        model_settings["openai_previous_response_id"] = openai_previous_response_id

    return model_settings


class ModelConfig(BaseModel):
    name: str
    temperature: float = 0.1
    settings: OpenAIModelSettings = Field(default_factory=OpenAIModelSettings)

    @field_validator("settings", mode="before")
    @classmethod
    def _coerce_oauth_settings(cls, settings: object) -> object:
        if isinstance(settings, OAuthResponsesSettings):
            return OpenAIModelSettings.from_oauth_settings(settings)
        return settings


class ModelProvider(ABC):
    """Represents some model provider config than can be converted into pydantic-ai models."""

    @abstractmethod
    def build_model(self, *, model_config: ModelConfig) -> Model:
        """Build a pydantic-ai model instance from the provider."""


def get_openai_client(api_key: str | None, base_url: str | None) -> AsyncOpenAI:
    """Create an OpenAI client.

    Meant as a stable interface for avoiding depending on openai's library.
    """
    return AsyncOpenAI(
        api_key=api_key,
        base_url=base_url,
    )


@define
class BaseOpenAIModelProvider(ModelProvider, ABC):
    """Shared OpenAI provider behavior."""

    @abstractmethod
    def get_openai_client(self) -> AsyncOpenAI:
        """Return the OpenAI client used to build a provider."""

    def build_provider(self) -> OpenAIProvider:
        """Build the shared pydantic-ai provider wrapper."""
        return OpenAIProvider(openai_client=self.get_openai_client())

    def build_model_settings(self, *, model_config: ModelConfig) -> ModelSettings:
        """Build the model settings payload from the validated config."""
        return to_model_settings(model_config.settings, temperature=model_config.temperature)


@define(kw_only=True)
class OpenAIModelProvider(BaseOpenAIModelProvider):
    """Plain OpenAI platform provider."""

    openai_client: AsyncOpenAI

    @override
    def get_openai_client(self) -> AsyncOpenAI:
        return self.openai_client

    @override
    def build_model(self, *, model_config: ModelConfig) -> Model:
        return OpenAIChatModel(
            model_name=model_config.name,
            provider=self.build_provider(),
            settings=self.build_model_settings(model_config=model_config),
        )


@define(kw_only=True)
class OpenAIOAuthModelProvider(BaseOpenAIModelProvider):
    """OAuth-backed OpenAI provider using responses models by default."""

    store: OpenAIOAuthStore
    _oauth_manager: OpenAIOAuthManager | None = field(init=False, default=None)
    _oauth_client: AsyncOpenAI | None = field(init=False, default=None)
    _oauth_provider: OpenAIProvider | None = field(init=False, default=None)

    @override
    def get_openai_client(self) -> AsyncOpenAI:
        client = self._oauth_client
        if client is None:
            client = build_chatgpt_oauth_client(manager=self.oauth_manager)
            self._oauth_client = client
        return client

    @property
    def oauth_manager(self) -> OpenAIOAuthManager:
        """Return the lazily-created OAuth manager for this provider."""
        manager = self._oauth_manager
        if manager is None:
            manager = OpenAIOAuthManager(store=self.store)
            self._oauth_manager = manager
        return manager

    @override
    def build_provider(self) -> OpenAIProvider:
        provider = self._oauth_provider
        if provider is None:
            provider = OpenAIProvider(openai_client=self.get_openai_client())
            self._oauth_provider = provider
        return provider

    @override
    def build_model(self, *, model_config: ModelConfig) -> Model:
        if model_config.name not in OPENAI_OAUTH_ALLOWED_MODELS:
            message = f"Unsupported OpenAI OAuth model: {model_config.name}"
            raise OpenAIOAuthModelConstraintError(message)

        settings = model_config.settings

        if settings.openai_previous_response_id is not None:
            message = "openai_previous_response_id is not supported for OAuth"
            raise OpenAIOAuthSettingsConstraintError(message)
        if settings.openai_store is True:
            message = "openai_store must be false for OAuth"
            raise OpenAIOAuthSettingsConstraintError(message)
        if settings.openai_send_reasoning_ids is True:
            message = "openai_send_reasoning_ids must be false for OAuth"
            raise OpenAIOAuthSettingsConstraintError(message)

        oauth_settings = OpenAIModelSettings.from_oauth_settings(oauth_responses_settings())

        return OpenAIResponsesModel(
            model_name=model_config.name,
            provider=self.build_provider(),
            settings=to_model_settings(
                oauth_settings,
                temperature=model_config.temperature,
            ),
        )


@define(kw_only=True)
class OperatorAgent[InType: BaseModel, OutType: BaseModel]:
    """Operator agent instance."""

    provider: ModelProvider
    output_type: type[OutType]
    model_config: ModelConfig
    agent: Agent[None, OutType] = field(init=False)

    def __attrs_post_init__(self) -> None:
        """Initialize internal pydantic-ai agent."""
        self.agent = Agent(
            model=self.provider.build_model(model_config=self.model_config),
            output_type=self.output_type,
        )


class Communication:
    """Namespace for types handling agent communication rules.

    For understanding these states, one must remember the system can be formed from many
    agents operating in a tree-like structure, with agents sometimes recursively calling
    new subagents for some task/goal.

    These (sub)agents in the tree aren't disposed by default, as other agents might want
    to follow-up with questions/comments at times, and so on.
    """

    class _BaseComm(BaseModel): ...

    type ModelUnion[T: _BaseComm] = T
    """For checking all items inside the union."""

    class Deny(_BaseComm):
        """Denies request for communication in all cases."""

    class Allow(_BaseComm):
        """Allows request for comms. at some cases."""

        allow_all: bool = False
        """Allows comms. w/ all available agents."""

        allow_parent: bool = True
        """Allows comms. w/ agent that was invoker of the agent."""

        allow_invoked: bool = True
        """Allows comms. w/ subagents directly invoked by the agent."""

        allow_downwards: bool = False
        """Allow comms. with all subagents at a level below the agent in the tree.

        NOTE: this does not navigate at paralell branches from the agent, thus all paths
        covered by subagents (children) of the current agent are recursively allowed BUT
        this does not include neighboring branches, nor parent neighboring branches, and
        so on.
        """

        allow_upwards: bool = True
        """Allow comms. w/ all agents at upper levels in the tree.

        NOTE: this does not navigate at paralell branches from the agent, thus all paths
        covered by the parent of the current agent are recursively searched and allowed,
        BUT this does won't include neighboring branches, nor parent neighbor branches.
        """

        allow_neighbours: bool = False
        """Allow comms. with tree neighbor agents."""


type CommunicationState = Communication.ModelUnion[Communication.Deny | Communication.Allow]
"""Specifies what should happen when an agent attempts to communicate with another."""


class FilesystemScope(BaseModel):
    """Specifies some point in the local filesystem that is at scope for some task.

    Can have exclusions and other rules through `glob` property.
    """

    path: DirectoryPath
    glob: str = "*"


class _BasePermission(BaseModel): ...


class Permission:
    """Namespace for agent permission types."""

    type ModelUnion[T: _BasePermission] = T

    class Filesystem:
        """Agent permission types dealing with the filesystem."""

        class BaseFilesystemPermission(_BasePermission):
            """Permission that is scoped to a directory, and optionally with a glob."""

            scope: FilesystemScope

        class Read(BaseFilesystemPermission):
            """Local file reading within a `scope`."""

        class Edit(BaseFilesystemPermission):
            """Local file creation/modification/deletion.

            `write`, `modify`, `delete` fields are individual overrides for each subcase.
            """

            can_write: bool = True
            can_modify: bool = True
            can_delete: bool = True

    class Subagent(_BasePermission):
        """Subagent invocation/communication.

        Has overrides for adjustments.
        """

        can_invoke: bool = True

        # uses default 'allow' settings (only parent and immediate children)
        can_communicate: CommunicationState = Communication.Allow()


type PermissionType = Permission.ModelUnion[
    Permission.Filesystem.Read | Permission.Filesystem.Edit | Permission.Subagent
]
"""Union for kinds of permissions agents may have.

These permissions can be defined at these levels:
- system-level: Operator itself configured to have these permissions as base defaults
- agent-level: Agent defined within boundaries of these permissions
- override-level: User-granted overrides at given points, through agent requests or
                  manual user commands.
"""


class _BaseTemporalScope(BaseModel): ...


class TemporalScope:
    """Namespace for temporal scope types."""

    type ModelUnion[T: _BaseTemporalScope] = T

    class All(_BaseTemporalScope):
        """Scope for 'all of time'."""

    class Interval(_BaseTemporalScope):
        """An interval of time.

        Fields `starts_at` and `ends_at` are used for handling interval-esque objects.
        - If no starting point is set, interval is considered an 'expiration date', since
          it's always valid until `ends_at` arrives.
        - If no end point is set, interval is considered a 'countdown' which, until the
          value of `starts_at` arrives, will be invalid.
        - If both values aren't set, it's conceptually equal to 'TemporalScope.All'.
        """

        starts_at: datetime | None = Field(
            None,
            description="If set, scope is validated from this starting point.",
        )
        ends_at: datetime | None = Field(
            None,
            description="If set, scope is validated up to this starting point.",
        )

    class Session(_BaseTemporalScope):
        """A placeholder scope dealing with session lifecycle.

        It's particularly relevant for override cases where permissions should expire
        after an action occurs or the session finishes.
        """


type TemporalScopeType = TemporalScope.ModelUnion[
    TemporalScope.All | TemporalScope.Interval | TemporalScope.Session
]
"""Union for kinds of temporal scopes for time or step-bound objects."""


class PermissionItem(BaseModel):
    """Permission instance with additional metadata."""

    permission: PermissionType
    temporal_scope: TemporalScopeType


class PermissionSet(BaseModel):
    """A group of permission items for a certain scope (system/agent/etc)."""


class ObjectMetadata(BaseModel):
    """Metadata for objects sharing a common pattern.

    From which their pattern is: name + description + detail
    """

    name: str = Field(description="Short name, used as its identifier.")
    description: str = Field(description="Brief summary telling when to use the it.")
    detail: str = Field(
        description=(
            "Comprehensive text on procedures, comments, etc. for understanding "
            "and handling the information. May describe: best practices, bad patterns, "
            "object-specific instructions or comments, etc."
        ),
    )


class BaseForm(BaseModel):
    """Wrapper for BaseModel with utility functions."""

    def to_json(self) -> dict[str, Any]:
        """Convert instance to JSON-safe dictionary safely."""
        return self.model_dump(
            mode="json",
            warnings="error",
        )

    def get_title(self) -> str:
        """Get this object's title for usage in other places."""
        return self.__repr_name__()

    def to_markdown(self) -> str:
        """Transform serialized form of object into Markdown."""
        message = "BaseForm.to_markdown is not implemented yet"
        raise NotImplementedError(message)


class ToolsetAction[InType: BaseForm, OutType: BaseForm](BaseForm):
    metadata: ObjectMetadata
    input_model: InType
    output_model: OutType


class Toolset[InType: BaseForm, OutType: BaseForm](BaseForm):
    """Toolset for agent usage.

    Toolsets are groups of actions (tools) of the same domain/type. Actions' schemas are
    lazily-shown to agents for avoiding context usage. Actions have independent required
    permissions from each other.

    Tools (natively supported by many agents) differ in toolsets and actions, tools are
    a base construct which is abstracted/wrapped by toolsets+actions. Abstraction can be
    done differently depending on model for better results.

    Agents shouldn't make or edit these toolsets directly, it risks bypassing permissions.
    """

    metadata: ObjectMetadata
    actions: list[ToolsetAction[InType, OutType]]

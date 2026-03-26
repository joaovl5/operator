"""OpenAI client construction and non-OAuth provider helpers."""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Protocol, override

from attrs import define
from openai import AsyncOpenAI, Omit
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

from operator_core.providers import ModelProvider
from operator_shared.settings.main import OAuthSettings

from .types import OpenAIModelConfig, OpenAIModelSettings

if TYPE_CHECKING:
    from pydantic_ai import ModelSettings
    from pydantic_ai.models import Model

CHATGPT_CODEX_BASE_URL = "https://chatgpt.com/backend-api/codex"
OPERATOR_ORIGINATOR = "operator"
DEFAULT_REFRESH_BUFFER_MS = OAuthSettings().refresh_buffer_ms
MISSING_CREDENTIALS_MESSAGE = "OpenAI OAuth credentials are missing; log in again"
REFRESH_REJECTED_MESSAGE = "OpenAI OAuth credentials expired or were rejected; log in again"
REMOVED_CREDENTIALS_MESSAGE = "OpenAI OAuth credentials were removed; log in again"


class OpenAIOAuthCredentialsProtocol(Protocol):
    """Credential shape required by the ChatGPT OAuth client wrapper."""

    account_id: str | None


class OpenAIOAuthManagerProtocol(Protocol):
    """Manager shape required by the ChatGPT OAuth client wrapper."""

    @property
    def current_credentials(self) -> OpenAIOAuthCredentialsProtocol | None:
        """Return the latest credentials currently stored on disk, if any."""
        ...

    async def get_access_token(self) -> str:
        """Return a usable access token for ChatGPT-backed traffic."""
        ...


def get_openai_client(*, api_key: str | None, base_url: str | None) -> AsyncOpenAI:
    """Create an OpenAI client."""
    return AsyncOpenAI(api_key=api_key, base_url=base_url)


def oauth_responses_settings(*, openai_store: bool = False) -> OpenAIModelSettings:
    """Return safe stateless defaults for OAuth-backed Responses requests."""
    return OpenAIModelSettings.oauth_defaults(
        openai_store=openai_store,
        openai_send_reasoning_ids=False,
    )


def build_chatgpt_oauth_client(*, manager: OpenAIOAuthManagerProtocol) -> AsyncOpenAI:
    """Build an authenticated AsyncOpenAI client for the ChatGPT Codex backend."""
    return _ChatGPTOAuthClient(manager=manager)


class _ChatGPTOAuthClient(AsyncOpenAI):
    """AsyncOpenAI client configured for ChatGPT OAuth traffic."""

    def __init__(self, *, manager: OpenAIOAuthManagerProtocol) -> None:
        self._oauth_manager: OpenAIOAuthManagerProtocol = manager
        super().__init__(
            api_key=manager.get_access_token,
            base_url=CHATGPT_CODEX_BASE_URL,
            default_headers={"originator": OPERATOR_ORIGINATOR},
        )

    @property
    @override
    def default_headers(self) -> dict[str, str | Omit]:
        headers = super().default_headers
        credentials = self._oauth_manager.current_credentials

        if credentials is None or credentials.account_id is None:
            _ = headers.pop("ChatGPT-Account-Id", None)
        else:
            headers["ChatGPT-Account-Id"] = credentials.account_id

        return headers


@define
class BaseOpenAIModelProvider(ModelProvider[OpenAIModelConfig], ABC):
    """Shared OpenAI provider behavior."""

    @abstractmethod
    def get_openai_client(self) -> AsyncOpenAI:
        """Return the OpenAI client used to build a provider."""

    def build_provider(self) -> OpenAIProvider:
        """Build the shared pydantic-ai provider wrapper."""
        return OpenAIProvider(openai_client=self.get_openai_client())

    def build_model_settings(self, *, model_config: OpenAIModelConfig) -> ModelSettings:
        """Build the model settings payload from the validated config."""
        return model_config.settings.to_model_settings(temperature=model_config.temperature)


@define(kw_only=True)
class OpenAIModelProvider(BaseOpenAIModelProvider):
    """Plain OpenAI platform provider."""

    openai_client: AsyncOpenAI

    @override
    def get_openai_client(self) -> AsyncOpenAI:
        """Return the configured OpenAI client."""
        return self.openai_client

    @override
    def build_model(self, *, model_config: OpenAIModelConfig) -> Model:
        """Build a chat model for the configured OpenAI client."""
        return OpenAIChatModel(
            model_name=model_config.name,
            provider=self.build_provider(),
            settings=self.build_model_settings(model_config=model_config),
        )


__all__ = [
    "CHATGPT_CODEX_BASE_URL",
    "DEFAULT_REFRESH_BUFFER_MS",
    "MISSING_CREDENTIALS_MESSAGE",
    "OPERATOR_ORIGINATOR",
    "REFRESH_REJECTED_MESSAGE",
    "REMOVED_CREDENTIALS_MESSAGE",
    "BaseOpenAIModelProvider",
    "OpenAIModelProvider",
    "build_chatgpt_oauth_client",
    "get_openai_client",
    "oauth_responses_settings",
]

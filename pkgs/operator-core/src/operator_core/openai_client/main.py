"""Authenticated OpenAI client helpers for ChatGPT OAuth traffic."""

import asyncio
from typing import TYPE_CHECKING, override

from attrs import define
from openai import AsyncOpenAI, Omit

from operator_core.openai_oauth import (
    OpenAIOAuthCredentials,
    OpenAIOAuthReauthRequiredError,
    OpenAITokenResponse,
)
from operator_core.openai_oauth import (
    refresh_access_token as refresh_openai_access_token,
)
from operator_shared.settings.main import OAuthSettings
from operator_shared.time import epoch_ms

if TYPE_CHECKING:
    from operator_core.openai_store import OpenAIOAuthStore

from .types import OAuthResponsesSettings, RefreshAccessToken
from .utils import get_refresh_lock

CHATGPT_CODEX_BASE_URL = "https://chatgpt.com/backend-api/codex"
OPERATOR_ORIGINATOR = "operator"
DEFAULT_REFRESH_BUFFER_MS = OAuthSettings().refresh_buffer_ms
MISSING_CREDENTIALS_MESSAGE = "OpenAI OAuth credentials are missing; log in again"
REFRESH_REJECTED_MESSAGE = "OpenAI OAuth credentials expired or were rejected; log in again"
REMOVED_CREDENTIALS_MESSAGE = "OpenAI OAuth credentials were removed; log in again"


def _refresh_access_token(refresh_token: str) -> OpenAITokenResponse:
    return refresh_openai_access_token(refresh_token=refresh_token)


def oauth_responses_settings(*, openai_store: bool = False) -> OAuthResponsesSettings:
    """Return safe stateless defaults for OAuth-backed Responses requests."""
    return OAuthResponsesSettings(openai_store=openai_store)


@define(kw_only=True)
class OpenAIOAuthManager:
    """Loads, refreshes, and persists OAuth credentials for ChatGPT traffic."""

    store: OpenAIOAuthStore
    refresh_access_token: RefreshAccessToken = _refresh_access_token
    refresh_buffer_ms: int = DEFAULT_REFRESH_BUFFER_MS

    @property
    def current_credentials(self) -> OpenAIOAuthCredentials | None:
        """Return the latest credentials currently stored on disk, if any."""
        return self.store.load()

    async def get_access_token(self) -> str:
        """Return a usable access token, refreshing and persisting if needed."""
        credentials = self._require_credentials()
        if not credentials.expires_within(
            now_ms=epoch_ms(),
            buffer_ms=self.refresh_buffer_ms,
        ):
            return credentials.access_token

        async with get_refresh_lock(store_path=self.store.path):
            credentials = self._require_credentials()
            if not credentials.expires_within(
                now_ms=epoch_ms(),
                buffer_ms=self.refresh_buffer_ms,
            ):
                return credentials.access_token

            return await self._refresh_credentials(credentials)

    def _require_credentials(self) -> OpenAIOAuthCredentials:
        credentials = self.store.load()
        if credentials is None:
            message = MISSING_CREDENTIALS_MESSAGE
            raise OpenAIOAuthReauthRequiredError(message)
        return credentials

    async def _refresh_credentials(self, credentials: OpenAIOAuthCredentials) -> str:
        try:
            token_response = await asyncio.to_thread(
                self.refresh_access_token,
                credentials.refresh_token,
            )
        except OpenAIOAuthReauthRequiredError as error:
            message = REFRESH_REJECTED_MESSAGE
            raise OpenAIOAuthReauthRequiredError(message) from error

        def persist_refresh(
            current: OpenAIOAuthCredentials | None,
        ) -> OpenAIOAuthCredentials:
            if current is None:
                message = REMOVED_CREDENTIALS_MESSAGE
                raise OpenAIOAuthReauthRequiredError(message)

            if current != credentials and not current.expires_within(
                now_ms=epoch_ms(),
                buffer_ms=self.refresh_buffer_ms,
            ):
                return current

            return token_response.to_credentials(
                now_ms=epoch_ms(),
                previous_credentials=current,
            )

        refreshed_credentials = self.store.update(persist_refresh)
        return refreshed_credentials.access_token


def build_chatgpt_oauth_client(*, manager: OpenAIOAuthManager) -> AsyncOpenAI:
    """Build an authenticated AsyncOpenAI client for the ChatGPT Codex backend."""
    return _ChatGPTOAuthClient(manager=manager)


class _ChatGPTOAuthClient(AsyncOpenAI):
    """AsyncOpenAI client configured for ChatGPT OAuth traffic."""

    def __init__(self, *, manager: OpenAIOAuthManager) -> None:
        self._oauth_manager: OpenAIOAuthManager = manager
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
            if "ChatGPT-Account-Id" in headers:
                del headers["ChatGPT-Account-Id"]
        else:
            headers["ChatGPT-Account-Id"] = credentials.account_id

        return headers

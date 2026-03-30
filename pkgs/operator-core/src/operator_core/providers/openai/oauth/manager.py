"""OpenAI OAuth credential refresh management."""

import asyncio
from typing import TYPE_CHECKING, Protocol

from attrs import define

from operator_core.providers.openai.errors import OpenAIOAuthReauthRequiredError
from operator_core.providers.utils.store.utils import get_async_path_lock
from operator_shared.time import epoch_ms

from .protocol import refresh_access_token

if TYPE_CHECKING:
    from .store import OpenAIOAuthStore
    from .types import OpenAIOAuthCredentials, OpenAITokenResponse

DEFAULT_REFRESH_BUFFER_MS = 60_000
MISSING_CREDENTIALS_MESSAGE = "OpenAI OAuth credentials are missing; log in again"
REFRESH_REJECTED_MESSAGE = "OpenAI OAuth credentials expired or were rejected; log in again"
REMOVED_CREDENTIALS_MESSAGE = "OpenAI OAuth credentials were removed; log in again"

class RefreshAccessToken(Protocol):
    """Keyword-only refresh hook used by the OAuth manager."""

    def __call__(self, *, refresh_token: str) -> OpenAITokenResponse:
        """Refresh an access token from the stored refresh token."""
        ...

def _refresh_access_token_default(*, refresh_token: str) -> OpenAITokenResponse:
    return refresh_access_token(refresh_token=refresh_token)


@define(kw_only=True)
class OpenAIOAuthManager:
    """Loads, refreshes, and persists OAuth credentials for ChatGPT traffic."""

    store: OpenAIOAuthStore
    refresh_access_token: RefreshAccessToken = _refresh_access_token_default
    refresh_buffer_ms: int = DEFAULT_REFRESH_BUFFER_MS

    @property
    def current_credentials(self) -> OpenAIOAuthCredentials | None:
        """Return the latest credentials currently stored on disk, if any."""
        return self.store.load()

    async def get_access_token(self) -> str:
        """Return a usable access token, refreshing and persisting if needed."""
        credentials = self._require_credentials()
        if not credentials.expires_within(now_ms=epoch_ms(), buffer_ms=self.refresh_buffer_ms):
            return credentials.access_token

        async with get_async_path_lock(path=self.store.path):
            credentials = self._require_credentials()
            if not credentials.expires_within(now_ms=epoch_ms(), buffer_ms=self.refresh_buffer_ms):
                return credentials.access_token

            return await self._refresh_credentials(credentials)

    def _require_credentials(self) -> OpenAIOAuthCredentials:
        credentials = self.store.load()
        if credentials is None:
            raise OpenAIOAuthReauthRequiredError(MISSING_CREDENTIALS_MESSAGE)
        return credentials

    async def _refresh_credentials(self, credentials: OpenAIOAuthCredentials) -> str:
        try:
            token_response = await asyncio.to_thread(
                self.refresh_access_token,
                refresh_token=credentials.refresh_token,
            )
        except OpenAIOAuthReauthRequiredError as error:
            raise OpenAIOAuthReauthRequiredError(REFRESH_REJECTED_MESSAGE) from error

        def persist_refresh(
            current: OpenAIOAuthCredentials | None,
        ) -> OpenAIOAuthCredentials:
            if current is None:
                raise OpenAIOAuthReauthRequiredError(REMOVED_CREDENTIALS_MESSAGE)

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
        if refreshed_credentials is None:
            raise OpenAIOAuthReauthRequiredError(REMOVED_CREDENTIALS_MESSAGE)
        return refreshed_credentials.access_token


__all__ = [
    "DEFAULT_REFRESH_BUFFER_MS",
    "MISSING_CREDENTIALS_MESSAGE",
    "REFRESH_REJECTED_MESSAGE",
    "REMOVED_CREDENTIALS_MESSAGE",
    "OpenAIOAuthManager",
]

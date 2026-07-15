"""ChatGPT Codex client helpers for OAuth-backed traffic."""

from typing import TYPE_CHECKING, Protocol, override

from openai import AsyncOpenAI, Omit

if TYPE_CHECKING:
  from .types import OpenAIOAuthCredentials

CHATGPT_CODEX_BASE_URL = "https://chatgpt.com/backend-api/codex"
OPERATOR_ORIGINATOR = "operator"


class OpenAIOAuthManagerProtocol(Protocol):
  """Manager shape required by the ChatGPT OAuth client wrapper."""

  @property
  def current_credentials(self) -> OpenAIOAuthCredentials | None:
    """Return the latest credentials currently stored on disk, if any."""
    ...

  async def get_access_token(self) -> str:
    """Return a usable access token for ChatGPT-backed traffic."""
    ...


def build_chatgpt_oauth_client(
  *, manager: OpenAIOAuthManagerProtocol
) -> AsyncOpenAI:
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


__all__ = [
  "CHATGPT_CODEX_BASE_URL",
  "OPERATOR_ORIGINATOR",
  "OpenAIOAuthManagerProtocol",
  "build_chatgpt_oauth_client",
]

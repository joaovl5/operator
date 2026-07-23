import asyncio
import inspect
import threading
from typing import TYPE_CHECKING

import pytest
from openai import AsyncOpenAI
from pydantic import BaseModel, ValidationError
from pydantic_ai.models.openai import (
  OpenAIChatModel,
  OpenAIResponsesModel,
)

from operator_core_olden.providers.openai import OpenAIModelProvider
from operator_core_olden.providers.openai.client import (
  get_openai_client,
)
from operator_core_olden.providers.openai.errors import (
  OpenAIOAuthReauthRequiredError,
)
from operator_core_olden.providers.openai.oauth.chatgpt import (
  CHATGPT_CODEX_BASE_URL,
  OPERATOR_ORIGINATOR,
  build_chatgpt_oauth_client,
)
from operator_core_olden.providers.openai.oauth.manager import (
  MISSING_CREDENTIALS_MESSAGE,
  REFRESH_REJECTED_MESSAGE,
  REMOVED_CREDENTIALS_MESSAGE,
  OpenAIOAuthManager,
)
from operator_core_olden.providers.openai.oauth.provider import (
  OpenAIOAuthModelProvider,
)
from operator_core_olden.providers.openai.oauth.settings import (
  OpenAIOAuthModelConfig,
  OpenAIOAuthModelSettings,
  oauth_responses_settings,
)
from operator_core_olden.providers.openai.oauth.store import (
  OpenAIOAuthStore,
)
from operator_core_olden.providers.openai.oauth.types import (
  OpenAIOAuthCredentials,
  OpenAITokenResponse,
)
from operator_core_olden.providers.openai.types import (
  DirectOpenAIModelConfig,
  OpenAIModelSettings,
)

if TYPE_CHECKING:
  from pathlib import Path

ACCESS_TOKEN = "oauth-access-token"  # noqa: S105
REFRESH_TOKEN = "oauth-refresh-token"  # noqa: S105
REFRESHED_ACCESS_TOKEN = "oauth-access-token-refreshed"  # noqa: S105
REFRESHED_REFRESH_TOKEN = "oauth-refresh-token-refreshed"  # noqa: S105
EXTERNAL_ACCESS_TOKEN = "oauth-access-token-external"  # noqa: S105
RELOGIN_ACCESS_TOKEN = "oauth-access-token-login"  # noqa: S105
RELOGIN_REFRESH_TOKEN = "oauth-refresh-token-login"  # noqa: S105
TOKEN_TYPE = "Bearer"  # noqa: S105
EXPECTED_EXPIRES_AT_MS = 60_000


def make_credentials(
  *,
  access_token: str = ACCESS_TOKEN,
  refresh_token: str = REFRESH_TOKEN,
  expires_at_ms: int | None = None,
  account_id: str | None = "acct_123",
) -> OpenAIOAuthCredentials:
  """Build representative OAuth credentials for client tests."""
  return OpenAIOAuthCredentials(
    access_token=access_token,
    refresh_token=refresh_token,
    expires_at_ms=expires_at_ms,
    account_id=account_id,
    scope="openid profile email offline_access",
    token_type=TOKEN_TYPE,
  )


def make_store(
  tmp_path: Path, credentials: OpenAIOAuthCredentials | None
) -> OpenAIOAuthStore:
  """Create a store optionally populated with credentials."""
  store = OpenAIOAuthStore(path=tmp_path / "openai.json")
  if credentials:
    _ = store.save(credentials)
  return store


def make_oauth_store(tmp_path: Path) -> OpenAIOAuthStore:
  """Create an OAuth store for provider tests."""
  return OpenAIOAuthStore(path=tmp_path / "openai.json")


@pytest.mark.parametrize(
  ("account_id", "expected_header"),
  [
    pytest.param("acct_123", "acct_123", id="account-present"),
    pytest.param(None, None, id="account-missing"),
  ],
)
def test_build_chatgpt_oauth_client_sets_codex_base_url_and_public_headers(
  tmp_path: Path,
  account_id: str | None,
  expected_header: str | None,
) -> None:
  """OAuth clients target ChatGPT Codex and expose account
  headers only when present."""
  store = make_store(
    tmp_path, make_credentials(account_id=account_id)
  )
  manager = OpenAIOAuthManager(store=store)

  client = build_chatgpt_oauth_client(manager=manager)

  assert str(client.base_url) == f"{CHATGPT_CODEX_BASE_URL}/"
  assert client.default_headers["originator"] == OPERATOR_ORIGINATOR
  if expected_header is None:
    assert "ChatGPT-Account-Id" not in client.default_headers
  else:
    assert (
      client.default_headers["ChatGPT-Account-Id"] == expected_header
    )


def test_oauth_manager_refreshes_expired_credentials_and_persists_them(
  monkeypatch: pytest.MonkeyPatch,
  tmp_path: Path,
) -> None:
  """Expired credentials refresh lazily and persist through the
  store."""
  monkeypatch.setattr(
    "operator_shared.time.utils.time.time", lambda: 0.0
  )
  store = make_store(tmp_path, make_credentials(expires_at_ms=0))

  def refresh(*, refresh_token: str) -> OpenAITokenResponse:
    assert refresh_token == REFRESH_TOKEN
    return OpenAITokenResponse(
      access_token=REFRESHED_ACCESS_TOKEN,
      refresh_token=REFRESHED_REFRESH_TOKEN,
      expires_in=60,
      token_type=TOKEN_TYPE,
    )

  manager = OpenAIOAuthManager(
    store=store,
    refresh_access_token=refresh,
    refresh_buffer_ms=1_000,
  )

  token = asyncio.run(manager.get_access_token())
  persisted = store.load()

  assert token == REFRESHED_ACCESS_TOKEN
  assert persisted
  assert persisted.access_token == REFRESHED_ACCESS_TOKEN
  assert persisted.refresh_token == REFRESHED_REFRESH_TOKEN
  assert persisted.expires_at_ms == EXPECTED_EXPIRES_AT_MS


def test_oauth_manager_serializes_refresh_across_concurrent_callers(
  monkeypatch: pytest.MonkeyPatch,
  tmp_path: Path,
) -> None:
  """Concurrent callers share a single refresh result for one
  store."""
  monkeypatch.setattr(
    "operator_shared.time.utils.time.time", lambda: 0.0
  )
  store = make_store(tmp_path, make_credentials(expires_at_ms=0))
  refresh_started = threading.Event()
  refresh_release = threading.Event()
  refresh_calls = 0

  def refresh(*, refresh_token: str) -> OpenAITokenResponse:
    nonlocal refresh_calls
    assert refresh_token == REFRESH_TOKEN
    refresh_calls += 1
    refresh_started.set()
    assert refresh_release.wait(timeout=1)
    return OpenAITokenResponse(
      access_token=REFRESHED_ACCESS_TOKEN,
      refresh_token=REFRESHED_REFRESH_TOKEN,
      expires_in=60,
      token_type=TOKEN_TYPE,
    )

  manager = OpenAIOAuthManager(
    store=store,
    refresh_access_token=refresh,
    refresh_buffer_ms=1_000,
  )

  async def run_test() -> None:
    first = asyncio.create_task(manager.get_access_token())
    _ = await asyncio.to_thread(refresh_started.wait, 1)
    second = asyncio.create_task(manager.get_access_token())
    refresh_release.set()

    assert await first == REFRESHED_ACCESS_TOKEN
    assert await second == REFRESHED_ACCESS_TOKEN

  _ = asyncio.run(run_test())

  assert refresh_calls == 1


def test_oauth_manager_serializes_refresh_across_managers_sharing_one_store(
  monkeypatch: pytest.MonkeyPatch,
  tmp_path: Path,
) -> None:
  """Separate managers over one store share the same persisted
  refresh result."""
  monkeypatch.setattr(
    "operator_shared.time.utils.time.time", lambda: 0.0
  )
  store = make_store(tmp_path, make_credentials(expires_at_ms=0))
  refresh_started = threading.Event()
  refresh_release = threading.Event()
  refresh_calls = 0

  def refresh(*, refresh_token: str) -> OpenAITokenResponse:
    nonlocal refresh_calls
    assert refresh_token == REFRESH_TOKEN
    refresh_calls += 1
    refresh_started.set()
    assert refresh_release.wait(timeout=1)
    return OpenAITokenResponse(
      access_token=REFRESHED_ACCESS_TOKEN,
      refresh_token=REFRESHED_REFRESH_TOKEN,
      expires_in=60,
      token_type=TOKEN_TYPE,
    )

  first_manager = OpenAIOAuthManager(
    store=store,
    refresh_access_token=refresh,
    refresh_buffer_ms=1_000,
  )
  second_manager = OpenAIOAuthManager(
    store=store,
    refresh_access_token=refresh,
    refresh_buffer_ms=1_000,
  )

  async def run_test() -> None:
    first = asyncio.create_task(first_manager.get_access_token())
    _ = await asyncio.to_thread(refresh_started.wait, 1)
    second = asyncio.create_task(second_manager.get_access_token())
    refresh_release.set()

    assert await first == REFRESHED_ACCESS_TOKEN
    assert await second == REFRESHED_ACCESS_TOKEN

  _ = asyncio.run(run_test())

  assert refresh_calls == 1


def test_oauth_manager_observes_external_store_updates_and_deletes(
  tmp_path: Path,
) -> None:
  """Managers read the store each time instead of holding stale
  credential snapshots."""
  store = make_store(tmp_path, make_credentials(expires_at_ms=None))
  manager = OpenAIOAuthManager(store=store)

  assert asyncio.run(manager.get_access_token()) == ACCESS_TOKEN

  _ = store.save(
    make_credentials(
      access_token=EXTERNAL_ACCESS_TOKEN, expires_at_ms=None
    )
  )

  assert (
    asyncio.run(manager.get_access_token()) == EXTERNAL_ACCESS_TOKEN
  )

  store.delete()

  with pytest.raises(
    OpenAIOAuthReauthRequiredError, match="log in again"
  ):
    _ = asyncio.run(manager.get_access_token())


def test_oauth_manager_requires_credentials_when_store_is_empty(
  tmp_path: Path,
) -> None:
  """Missing credentials produce the focused public re-login error."""
  manager = OpenAIOAuthManager(store=make_store(tmp_path, None))

  with pytest.raises(
    OpenAIOAuthReauthRequiredError, match=MISSING_CREDENTIALS_MESSAGE
  ):
    _ = asyncio.run(manager.get_access_token())


def test_oauth_manager_normalizes_refresh_auth_failures(
  tmp_path: Path,
) -> None:
  """Refresh auth failures are converted into the public
  re-login message."""
  store = make_store(tmp_path, make_credentials(expires_at_ms=0))

  def fail_refresh(*, refresh_token: str) -> OpenAITokenResponse:
    del refresh_token
    message = "needs re-login"
    raise OpenAIOAuthReauthRequiredError(message)

  manager = OpenAIOAuthManager(
    store=store, refresh_access_token=fail_refresh
  )

  with pytest.raises(
    OpenAIOAuthReauthRequiredError, match=REFRESH_REJECTED_MESSAGE
  ):
    _ = asyncio.run(manager.get_access_token())


def test_delete_during_refresh_leaves_store_empty(
  monkeypatch: pytest.MonkeyPatch,
  tmp_path: Path,
) -> None:
  """Deleting credentials during refresh does not resurrect
  stale state."""
  monkeypatch.setattr(
    "operator_shared.time.utils.time.time", lambda: 0.0
  )
  store = make_store(tmp_path, make_credentials(expires_at_ms=0))
  refresh_started = threading.Event()
  refresh_release = threading.Event()

  def refresh(*, refresh_token: str) -> OpenAITokenResponse:
    assert refresh_token == REFRESH_TOKEN
    refresh_started.set()
    assert refresh_release.wait(timeout=1)
    return OpenAITokenResponse(
      access_token=REFRESHED_ACCESS_TOKEN,
      refresh_token=REFRESHED_REFRESH_TOKEN,
      expires_in=60,
      token_type=TOKEN_TYPE,
    )

  manager = OpenAIOAuthManager(
    store=store,
    refresh_access_token=refresh,
    refresh_buffer_ms=1_000,
  )

  async def run_test() -> None:
    task = asyncio.create_task(manager.get_access_token())
    _ = await asyncio.to_thread(refresh_started.wait, 1)
    store.delete()
    refresh_release.set()

    with pytest.raises(
      OpenAIOAuthReauthRequiredError,
      match=REMOVED_CREDENTIALS_MESSAGE,
    ):
      await task

  _ = asyncio.run(run_test())

  assert store.load() is None


def test_newer_credentials_win_over_stale_refresh_results(
  monkeypatch: pytest.MonkeyPatch,
  tmp_path: Path,
) -> None:
  """A concurrent relogin is kept instead of being overwritten
  by stale refresh output."""
  monkeypatch.setattr(
    "operator_shared.time.utils.time.time", lambda: 0.0
  )
  store = make_store(tmp_path, make_credentials(expires_at_ms=0))
  refresh_started = threading.Event()
  refresh_release = threading.Event()

  def refresh(*, refresh_token: str) -> OpenAITokenResponse:
    assert refresh_token == REFRESH_TOKEN
    refresh_started.set()
    assert refresh_release.wait(timeout=1)
    return OpenAITokenResponse(
      access_token=REFRESHED_ACCESS_TOKEN,
      refresh_token=REFRESHED_REFRESH_TOKEN,
      expires_in=60,
      token_type=TOKEN_TYPE,
    )

  manager = OpenAIOAuthManager(
    store=store,
    refresh_access_token=refresh,
    refresh_buffer_ms=1_000,
  )

  async def run_test() -> None:
    task = asyncio.create_task(manager.get_access_token())
    _ = await asyncio.to_thread(refresh_started.wait, 1)
    store.delete()
    _ = store.save(
      make_credentials(
        access_token=RELOGIN_ACCESS_TOKEN,
        refresh_token=RELOGIN_REFRESH_TOKEN,
        expires_at_ms=None,
      )
    )
    refresh_release.set()

    assert await task == RELOGIN_ACCESS_TOKEN

  _ = asyncio.run(run_test())

  persisted = store.load()
  assert persisted
  assert persisted.access_token == RELOGIN_ACCESS_TOKEN
  assert persisted.refresh_token == RELOGIN_REFRESH_TOKEN


def test_oauth_responses_settings_return_validated_serializable_model() -> (
  None
):
  """OAuth responses defaults are a serializable model, not an
  ad-hoc typed dict."""
  signature = inspect.signature(oauth_responses_settings)
  assert signature.parameters == {}

  settings = oauth_responses_settings()

  assert isinstance(settings, BaseModel)
  assert isinstance(settings, OpenAIOAuthModelSettings)
  assert settings.model_dump(mode="json", exclude_none=True) == {
    "openai_store": False,
    "openai_send_reasoning_ids": False,
  }

  with pytest.raises(ValidationError, match="unexpected"):
    _ = settings.__class__.model_validate(
      {
        "openai_store": False,
        "openai_send_reasoning_ids": False,
        "unexpected": True,
      }
    )


def test_openai_oauth_model_config_and_provider_build_responses_models(
  tmp_path: Path,
) -> None:
  """OAuth provider uses a validated OAuth config boundary to
  build responses models."""
  provider = OpenAIOAuthModelProvider(
    store=make_oauth_store(tmp_path)
  )

  with pytest.raises(ValidationError, match="openai_store"):
    _ = OpenAIOAuthModelConfig.model_validate(
      {
        "name": "gpt-5.3-codex",
        "settings": {"openai_store": True},
      }
    )

  with pytest.raises(ValidationError, match=r"gpt-4\.1"):
    _ = OpenAIOAuthModelConfig.model_validate({"name": "gpt-4.1"})

  model = provider.build_model(
    model_config=OpenAIOAuthModelConfig(name="gpt-5.3-codex")
  )

  assert isinstance(model, OpenAIResponsesModel)
  assert model.settings
  assert dict(model.settings.items())["openai_store"] is False


def test_openai_and_oauth_providers_build_public_model_types(
  tmp_path: Path,
) -> None:
  """Plain OpenAI providers build chat models while OAuth
  providers build responses models."""
  openai_model = OpenAIModelProvider(
    openai_client=AsyncOpenAI(api_key="test-api-key")
  ).build_model(
    model_config=DirectOpenAIModelConfig(
      name="gpt-4.1",
      temperature=0.7,
      settings=OpenAIModelSettings(openai_store=True),
    )
  )
  oauth_model = OpenAIOAuthModelProvider(
    store=make_oauth_store(tmp_path)
  ).build_model(
    model_config=OpenAIOAuthModelConfig(name="gpt-5.3-codex")
  )

  assert isinstance(openai_model, OpenAIChatModel)
  assert openai_model.settings
  assert dict(openai_model.settings.items())["openai_store"] is True
  assert isinstance(oauth_model, OpenAIResponsesModel)


def test_public_openai_client_helpers_match_workspace_api_conventions() -> (
  None
):
  """Public provider helpers keep keyword-only arguments and real
  docstrings."""
  signature = inspect.signature(get_openai_client)
  assert (
    signature.parameters["api_key"].kind
    is inspect.Parameter.KEYWORD_ONLY
  )
  assert (
    signature.parameters["base_url"].kind
    is inspect.Parameter.KEYWORD_ONLY
  )

  oauth_client_signature = inspect.signature(
    build_chatgpt_oauth_client
  )
  assert (
    oauth_client_signature.parameters["manager"].kind
    is inspect.Parameter.KEYWORD_ONLY
  )
  assert inspect.signature(oauth_responses_settings).parameters == {}

  for method in (
    OpenAIModelProvider.get_openai_client,
    OpenAIModelProvider.build_model,
    build_chatgpt_oauth_client,
    OpenAIOAuthModelProvider.get_openai_client,
    OpenAIOAuthModelProvider.build_provider,
    OpenAIOAuthModelProvider.build_model,
  ):
    assert method.__doc__
    assert method.__doc__.strip()

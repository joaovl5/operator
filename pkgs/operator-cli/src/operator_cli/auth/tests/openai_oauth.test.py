from http.server import ThreadingHTTPServer
from threading import Event, Lock, Thread
from typing import TYPE_CHECKING, final
from urllib.parse import parse_qs, urlencode, urlsplit

import httpx
import pytest

from operator_cli.auth.errors import (
  CallbackListenerTimeoutError,
  CallbackParseError,
  CallbackStateMismatchError,
)
from operator_cli.auth.listener import (
  _CallbackHTTPServer,
  _LocalhostCallbackListener,
  create_callback_listener,
  parse_callback_query,
)
from operator_cli.auth.main import run_openai_login
from operator_cli.auth.openai_oauth import (
  default_login_flow_dependencies,
  parse_callback_url,
  validate_callback_payload,
)
from operator_cli.auth.types import (
  BrowserOpen,
  CallbackListenerFactory,
  CallbackPayload,
  ExchangeAuthorizationCode,
  InputText,
  LoginFlowDependencies,
  Output,
)
from operator_core_olden.providers.openai import (
  OpenAIOAuthReauthRequiredError,
  OpenAIOAuthStore,
  OpenAITokenResponse,
)
from operator_shared.settings import (
  CallbackSettings,
  OAuthSettings,
  OperatorSettings,
)

from .support import (
  ACCESS_TOKEN,
  EXPECTED_ACCOUNT_ID,
  make_token_response,
)

if TYPE_CHECKING:
  from pathlib import Path
  from types import TracebackType
EXPECTED_STATE = "expected-state"
CALLBACK_CODE = "callback-code"
MANUAL_CODE = "manual-code"
CALLBACK_TIMEOUT_SECONDS = 7


def make_settings() -> OperatorSettings:
  """Build focused settings fixtures for the CLI auth flow."""
  return OperatorSettings(
    oauth=OAuthSettings(
      callback=CallbackSettings(
        port=1455,
        path="/auth/callback",
      )
    )
  )


def make_callback_url(
  *, code: str, state: str, settings: OperatorSettings
) -> str:
  """Build a callback URL matching the configured redirect URI."""
  query = urlencode({"code": code, "state": state})
  return f"{settings.oauth.callback.redirect_uri()}?{query}"


@final
class FakeListener:
  """Test callback listener with an injected result."""

  def __init__(self, result: CallbackPayload | Exception) -> None:
    """Store the callback result returned by the fake listener."""
    self._result = result
    self.closed = False
    self.timeout_seconds: int | None = None

  def wait_for_callback(
    self, *, timeout_seconds: int
  ) -> CallbackPayload:
    """Return the injected callback payload or raise the
    injected error.
    """
    self.timeout_seconds = timeout_seconds
    if isinstance(self._result, Exception):
      raise self._result
    return self._result

  def close(self) -> None:
    """Record that the fake listener was closed."""
    self.closed = True


@final
class ControlledLock:
  """Lock wrapper that lets a test force two concurrent
  capture attempts.
  """

  def __init__(self) -> None:
    "Initialize the lock wrapper state used by the concurrency test."
    self._lock = Lock()
    self.first_entered = Event()
    self.release_first = Event()
    self._enter_count = 0

  def __enter__(self) -> None:
    """Acquire the lock and optionally block the first entrant."""
    assert self._lock.acquire(timeout=1)
    self._enter_count += 1
    if self._enter_count == 1:
      self.first_entered.set()
      assert self.release_first.wait(timeout=1)

  def __exit__(
    self,
    type_: type[BaseException] | None,
    value: BaseException | None,
    traceback: TracebackType | None,
    /,
  ) -> None:
    "Release the wrapped lock after the critical section completes."
    del type_, value, traceback
    self._lock.release()


def make_listener_factory(
  listener: FakeListener,
) -> CallbackListenerFactory:
  """Return a typed listener factory for a fixed fake listener."""

  def listener_factory(
    *,
    bind_host: str,
    port: int,
    path: str,
    pending_state: str,
  ) -> FakeListener:
    del bind_host, port, path, pending_state
    return listener

  return listener_factory


def make_login_dependencies(
  *,
  listener_factory: CallbackListenerFactory,
  browser_open: BrowserOpen,
  exchange_code: ExchangeAuthorizationCode,
  input_text: InputText,
  output: Output,
) -> LoginFlowDependencies:
  """Build login dependencies with focused test doubles."""
  return LoginFlowDependencies(
    listener_factory=listener_factory,
    browser_open=browser_open,
    exchange_code=exchange_code,
    input_text=input_text,
    output=output,
    state_factory=lambda: EXPECTED_STATE,
    timeout_seconds=CALLBACK_TIMEOUT_SECONDS,
  )


def exchange_success(
  *, code: str, code_verifier: str, redirect_uri: str
) -> OpenAITokenResponse:
  """Return a successful token exchange fixture."""
  del code, code_verifier, redirect_uri
  return make_token_response()


def browser_opens(_url: str) -> bool:
  """Return a successful browser-open result."""
  return True


def browser_fails(_url: str) -> bool:
  """Return a failed browser-open result."""
  return False


def unexpected_browser_open(_url: str) -> bool:
  """Fail fast when a test unexpectedly tries opening a browser."""
  message = "browser should not open"
  raise AssertionError(message)


def manual_callback_input(*, settings: OperatorSettings) -> InputText:
  "Build a manual callback input function with the expected state."

  def input_text(_prompt: str) -> str:
    return make_callback_url(
      code=MANUAL_CODE,
      state=EXPECTED_STATE,
      settings=settings,
    )

  return input_text


def ignore_output(_line: str) -> None:
  """Discard test output lines."""
  return


def exchange_requires_relogin(
  *, code: str, code_verifier: str, redirect_uri: str
) -> OpenAITokenResponse:
  "Raise the focused re-login error surfaced by the core OAuth layer."
  del code, code_verifier, redirect_uri
  message = "needs re-login"
  raise OpenAIOAuthReauthRequiredError(message)


def exchange_missing_account(
  *, code: str, code_verifier: str, redirect_uri: str
) -> OpenAITokenResponse:
  """Return a successful token exchange without an account claim."""
  del code, code_verifier, redirect_uri
  return make_token_response(account_id=None)


def exchange_missing_refresh_token(
  *, code: str, code_verifier: str, redirect_uri: str
) -> OpenAITokenResponse:
  """Return a token response that fails conversion into
  stored credentials.
  """
  del code, code_verifier, redirect_uri
  return OpenAITokenResponse(
    access_token=ACCESS_TOKEN, refresh_token=None
  )


def unexpected_input(_prompt: str) -> str:
  """Fail fast when a test unexpectedly enters manual mode."""
  message = f"unexpected prompt: {_prompt}"
  raise AssertionError(message)


def test_default_login_flow_uses_dedicated_listener_module() -> None:
  """The production dependency bundle is assembled from the
  listener module.
  """
  assert default_login_flow_dependencies().listener_factory is (
    create_callback_listener
  )


def test_login_uses_fixed_localhost_binding_and_redirect_uri(
  tmp_path: Path,
) -> None:
  """Login binds the listener to localhost and uses the fixed
  localhost redirect URI.
  """
  settings = make_settings()
  store = OpenAIOAuthStore(path=tmp_path / "openai.json")
  listener = FakeListener(
    CallbackPayload(code=CALLBACK_CODE, state=EXPECTED_STATE)
  )
  output_lines: list[str] = []
  seen_bind_hosts: list[str] = []
  seen_urls: list[str] = []

  def listener_factory(
    *,
    bind_host: str,
    port: int,
    path: str,
    pending_state: str,
  ) -> FakeListener:
    seen_bind_hosts.append(bind_host)
    assert port == settings.oauth.callback.port
    assert path == settings.oauth.callback.path
    assert pending_state == EXPECTED_STATE
    return listener

  def browser_open(url: str) -> bool:
    seen_urls.append(url)
    return True

  result = run_openai_login(
    store=store,
    settings=settings,
    dependencies=make_login_dependencies(
      listener_factory=listener_factory,
      browser_open=browser_open,
      exchange_code=exchange_success,
      input_text=unexpected_input,
      output=output_lines.append,
    ),
  )

  credentials = store.load()
  redirect_uri = parse_qs(urlsplit(seen_urls[0]).query)[
    "redirect_uri"
  ][0]

  assert result == 0
  assert credentials
  assert credentials.account_id == EXPECTED_ACCOUNT_ID
  assert seen_bind_hosts == ["localhost"]
  assert redirect_uri == settings.oauth.callback.redirect_uri()
  assert urlsplit(redirect_uri).hostname == "localhost"


def test_login_persists_credentials_from_localhost_callback(
  tmp_path: Path,
) -> None:
  """Successful login stores exchanged credentials and closes
  the listener.
  """
  settings = make_settings()
  store = OpenAIOAuthStore(path=tmp_path / "openai.json")
  listener = FakeListener(
    CallbackPayload(code=CALLBACK_CODE, state=EXPECTED_STATE)
  )
  output_lines: list[str] = []

  result = run_openai_login(
    store=store,
    settings=settings,
    dependencies=make_login_dependencies(
      listener_factory=make_listener_factory(listener),
      browser_open=browser_opens,
      exchange_code=exchange_success,
      input_text=unexpected_input,
      output=output_lines.append,
    ),
  )

  credentials = store.load()

  assert result == 0
  assert credentials
  assert credentials.access_token == ACCESS_TOKEN
  assert credentials.account_id == EXPECTED_ACCOUNT_ID
  assert listener.closed is True
  assert "complete" in "\n".join(output_lines).lower()


def test_run_openai_login_port_in_use_falls_back_to_manual_mode(
  tmp_path: Path,
) -> None:
  """Port conflicts skip the listener and prompt for manual
  callback entry.
  """
  settings = make_settings()
  store = OpenAIOAuthStore(path=tmp_path / "openai.json")
  output_lines: list[str] = []

  def listener_factory(
    *,
    bind_host: str,
    port: int,
    path: str,
    pending_state: str,
  ) -> FakeListener:
    del bind_host, port, path, pending_state
    raise OSError(98, "Address already in use")

  result = run_openai_login(
    store=store,
    settings=settings,
    dependencies=make_login_dependencies(
      listener_factory=listener_factory,
      browser_open=unexpected_browser_open,
      exchange_code=exchange_success,
      input_text=manual_callback_input(settings=settings),
      output=output_lines.append,
    ),
  )

  assert result == 0
  assert store.load()
  assert "manual" in "\n".join(output_lines).lower()


def test_listener_start_failure_falls_back_to_manual_mode(
  tmp_path: Path,
) -> None:
  """Non-port-conflict listener startup failures still fall
  back to manual mode.
  """
  settings = make_settings()
  store = OpenAIOAuthStore(path=tmp_path / "openai.json")
  output_lines: list[str] = []

  def listener_factory(
    *,
    bind_host: str,
    port: int,
    path: str,
    pending_state: str,
  ) -> FakeListener:
    del bind_host, port, path, pending_state
    raise PermissionError(13, "Permission denied")

  result = run_openai_login(
    store=store,
    settings=settings,
    dependencies=make_login_dependencies(
      listener_factory=listener_factory,
      browser_open=unexpected_browser_open,
      exchange_code=exchange_success,
      input_text=manual_callback_input(settings=settings),
      output=output_lines.append,
    ),
  )

  assert result == 0
  assert store.load()
  assert "manual" in "\n".join(output_lines).lower()


def test_run_openai_login_browser_failure_falls_back_to_manual_mode(
  tmp_path: Path,
) -> None:
  """Browser launch failures fall back to manual callback entry."""
  settings = make_settings()
  store = OpenAIOAuthStore(path=tmp_path / "openai.json")
  listener = FakeListener(
    CallbackPayload(code="unused", state=EXPECTED_STATE)
  )
  output_lines: list[str] = []

  result = run_openai_login(
    store=store,
    settings=settings,
    dependencies=make_login_dependencies(
      listener_factory=make_listener_factory(listener),
      browser_open=browser_fails,
      exchange_code=exchange_success,
      input_text=manual_callback_input(settings=settings),
      output=output_lines.append,
    ),
  )

  assert result == 0
  assert store.load()
  assert listener.closed is True
  assert "browser" in "\n".join(output_lines).lower()


def test_run_openai_login_timeout_falls_back_to_manual_mode(
  tmp_path: Path,
) -> None:
  """Listener timeouts fall back to manual callback entry."""
  settings = make_settings()
  store = OpenAIOAuthStore(path=tmp_path / "openai.json")
  listener = FakeListener(CallbackListenerTimeoutError("timed out"))
  output_lines: list[str] = []

  result = run_openai_login(
    store=store,
    settings=settings,
    dependencies=make_login_dependencies(
      listener_factory=make_listener_factory(listener),
      browser_open=browser_opens,
      exchange_code=exchange_success,
      input_text=manual_callback_input(settings=settings),
      output=output_lines.append,
    ),
  )

  assert result == 0
  assert store.load()
  assert listener.closed is True
  assert listener.timeout_seconds == CALLBACK_TIMEOUT_SECONDS
  assert "manual" in "\n".join(output_lines).lower()


@pytest.mark.parametrize(
  ("manual_state", "expected_message"),
  [
    pytest.param(
      "wrong-state", "state mismatch", id="manual-mismatch"
    ),
    pytest.param(
      None, "invalid openai callback input", id="invalid-manual-url"
    ),
  ],
)
def test_invalid_manual_callback_does_not_persist_credentials(
  tmp_path: Path,
  manual_state: str | None,
  expected_message: str,
) -> None:
  """Invalid manual callback input fails cleanly without
  storing credentials.
  """
  settings = make_settings()
  store = OpenAIOAuthStore(path=tmp_path / "openai.json")
  output_lines: list[str] = []

  def listener_factory(
    *,
    bind_host: str,
    port: int,
    path: str,
    pending_state: str,
  ) -> FakeListener:
    del bind_host, port, path, pending_state
    raise OSError(98, "Address already in use")

  if manual_state is None:

    def input_text(_prompt: str) -> str:
      return "not-a-url"
  else:

    def input_text(_prompt: str) -> str:
      return make_callback_url(
        code=MANUAL_CODE,
        state=manual_state,
        settings=settings,
      )

  result = run_openai_login(
    store=store,
    settings=settings,
    dependencies=make_login_dependencies(
      listener_factory=listener_factory,
      browser_open=unexpected_browser_open,
      exchange_code=exchange_success,
      input_text=input_text,
      output=output_lines.append,
    ),
  )

  assert result == 1
  assert store.load() is None
  assert expected_message in "\n".join(output_lines).lower()


def test_callback_validation_rejects_invalid_url_and_state() -> None:
  "Callback parsing and state validation fail with focused errors."
  settings = make_settings()

  payload = parse_callback_url(
    make_callback_url(
      code=CALLBACK_CODE, state=EXPECTED_STATE, settings=settings
    ),
    callback=settings.oauth.callback,
  )

  assert payload == CallbackPayload(
    code=CALLBACK_CODE, state=EXPECTED_STATE
  )

  with pytest.raises(
    CallbackParseError, match="callback URL path must be"
  ):
    _ = parse_callback_url(
      "http://localhost:1455/wrong-path?code=x&state=y",
      callback=settings.oauth.callback,
    )

  with pytest.raises(
    CallbackParseError, match="callback URL must use"
  ):
    _ = parse_callback_url(
      "https://example.com/auth/callback?code=x&state=y",
      callback=settings.oauth.callback,
    )

  with pytest.raises(
    CallbackParseError, match="expected a full callback URL"
  ):
    _ = parse_callback_url(
      "http://localhost:not-a-port/auth/callback?code=x&state=y",
      callback=settings.oauth.callback,
    )

  with pytest.raises(CallbackStateMismatchError):
    _ = validate_callback_payload(
      payload, pending_state="wrong-state"
    )


def test_malformed_callback_query_raises_parse_error() -> None:
  """Malformed query strings become a user-facing parse error."""
  with pytest.raises(CallbackParseError):
    _ = parse_callback_query(query="a=1&%")


def test_missing_callback_query_values_raise_parse_error() -> None:
  """Missing query fields are translated to typed callback
  parse errors.
  """
  with pytest.raises(
    CallbackParseError, match="callback URL is missing code"
  ):
    _ = parse_callback_query(query="state=abc")

  with pytest.raises(
    CallbackParseError, match="callback URL is missing state"
  ):
    _ = parse_callback_query(query="code=abc")


def test_parse_callback_query_returns_payload_for_valid_input() -> (
  None
):
  """A valid callback query yields a typed payload."""
  payload = parse_callback_query(query="code=abc&state=xyz")

  assert payload == CallbackPayload(code="abc", state="xyz")


def test_callback_listener_keeps_first_valid_payload() -> None:
  """The localhost listener keeps the first callback payload
  it captures.
  """
  listener = _LocalhostCallbackListener(
    bind_host="127.0.0.1",
    port=0,
    path="/auth/callback",
    pending_state=EXPECTED_STATE,
  )

  try:
    first = CallbackPayload(code="first-code", state="first-state")
    second = CallbackPayload(code="second-code", state="second-state")

    listener.set_payload(first)
    listener.set_payload(second)

    assert listener.wait_for_callback(timeout_seconds=0) == first
  finally:
    listener.close()


def test_concurrent_callback_capture_keeps_first_payload() -> None:
  """Concurrent callback capture still preserves the first payload."""
  listener = _LocalhostCallbackListener(
    bind_host="127.0.0.1",
    port=0,
    path="/auth/callback",
    pending_state=EXPECTED_STATE,
  )
  controlled_lock = ControlledLock()
  listener._state.payload_lock = controlled_lock

  try:
    first = CallbackPayload(code="first-code", state="first-state")
    second = CallbackPayload(code="second-code", state="second-state")
    first_thread = Thread(target=listener.set_payload, args=(first,))
    second_thread = Thread(
      target=listener.set_payload, args=(second,)
    )

    first_thread.start()
    assert controlled_lock.first_entered.wait(timeout=1)
    second_thread.start()
    controlled_lock.release_first.set()
    first_thread.join(timeout=1)
    second_thread.join(timeout=1)

    assert not first_thread.is_alive()
    assert not second_thread.is_alive()
    assert listener.wait_for_callback(timeout_seconds=0) == first
  finally:
    listener.close()


def test_callback_listener_uses_threaded_http_server() -> None:
  """The localhost listener transport uses a threaded
  reusable HTTP server.
  """
  assert issubclass(_CallbackHTTPServer, ThreadingHTTPServer)
  assert _CallbackHTTPServer.daemon_threads is True
  assert _CallbackHTTPServer.allow_reuse_address is True


def test_listener_ignores_wrong_state_until_matching_callback() -> (
  None
):
  """The live listener ignores wrong-state callbacks until a
  matching one arrives.
  """
  listener = _LocalhostCallbackListener(
    bind_host="127.0.0.1",
    port=0,
    path="/auth/callback",
    pending_state=EXPECTED_STATE,
  )

  try:
    port = listener._server.server_address[1]
    with httpx.Client() as client:
      wrong_response = client.get(
        f"http://127.0.0.1:{port}/auth/callback",
        params={"code": "wrong-code", "state": "wrong-state"},
      )
      valid_response = client.get(
        f"http://127.0.0.1:{port}/auth/callback",
        params={"code": CALLBACK_CODE, "state": EXPECTED_STATE},
      )

    assert wrong_response.status_code == 400
    assert valid_response.status_code == 200
    assert listener.wait_for_callback(
      timeout_seconds=1
    ) == CallbackPayload(
      code=CALLBACK_CODE,
      state=EXPECTED_STATE,
    )
  finally:
    listener.close()


def test_relogin_guidance_does_not_persist_credentials(
  tmp_path: Path,
) -> None:
  """Token exchange auth failures return guidance instead of
  storing partial state.
  """
  settings = make_settings()
  store = OpenAIOAuthStore(path=tmp_path / "openai.json")
  output_lines: list[str] = []
  listener = FakeListener(
    CallbackPayload(code=CALLBACK_CODE, state=EXPECTED_STATE)
  )

  result = run_openai_login(
    store=store,
    settings=settings,
    dependencies=make_login_dependencies(
      listener_factory=make_listener_factory(listener),
      browser_open=browser_opens,
      exchange_code=exchange_requires_relogin,
      input_text=unexpected_input,
      output=output_lines.append,
    ),
  )

  assert result == 1
  assert store.load() is None
  assert "log in again" in "\n".join(output_lines).lower()


def test_protocol_failures_do_not_persist_credentials(
  tmp_path: Path,
) -> None:
  """Protocol failures become user-facing login failures
  without storing state.
  """
  settings = make_settings()
  store = OpenAIOAuthStore(path=tmp_path / "openai.json")
  output_lines: list[str] = []
  listener = FakeListener(
    CallbackPayload(code=CALLBACK_CODE, state=EXPECTED_STATE)
  )

  result = run_openai_login(
    store=store,
    settings=settings,
    dependencies=make_login_dependencies(
      listener_factory=make_listener_factory(listener),
      browser_open=browser_opens,
      exchange_code=exchange_missing_refresh_token,
      input_text=unexpected_input,
      output=output_lines.append,
    ),
  )

  assert result == 1
  assert store.load() is None
  assert "openai login failed" in "\n".join(output_lines).lower()


def test_run_openai_login_tolerates_missing_account_claims(
  tmp_path: Path,
) -> None:
  """Login still persists credentials when the token lacks a
  ChatGPT account claim.
  """
  settings = make_settings()
  store = OpenAIOAuthStore(path=tmp_path / "openai.json")
  listener = FakeListener(
    CallbackPayload(code=CALLBACK_CODE, state=EXPECTED_STATE)
  )

  result = run_openai_login(
    store=store,
    settings=settings,
    dependencies=make_login_dependencies(
      listener_factory=make_listener_factory(listener),
      browser_open=browser_opens,
      exchange_code=exchange_missing_account,
      input_text=unexpected_input,
      output=ignore_output,
    ),
  )

  credentials = store.load()

  assert result == 0
  assert credentials
  assert credentials.account_id is None

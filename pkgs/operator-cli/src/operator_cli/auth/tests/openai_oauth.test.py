import http.client
import importlib
import socket
from typing import TYPE_CHECKING, final
from urllib.parse import parse_qs, urlencode, urlsplit

import pytest

from operator_core.providers.openai import (
    OpenAIOAuthReauthRequiredError,
    OpenAIOAuthStore,
    OpenAITokenResponse,
)
from operator_shared.settings import CallbackSettings, OAuthSettings, OperatorSettings

from .support import ACCESS_TOKEN, EXPECTED_ACCOUNT_ID, make_token_response

if TYPE_CHECKING:
    from types import ModuleType


def load_auth_main() -> ModuleType:
    """Import the auth entrypoint module lazily for this test file."""
    return importlib.import_module("operator_cli.auth.main")


def load_openai_oauth() -> ModuleType:
    """Import the OpenAI OAuth helper module lazily for this test file."""
    return importlib.import_module("operator_cli.auth.openai_oauth")


types_module = importlib.import_module("operator_cli.auth.types")
BrowserOpen = types_module.BrowserOpen
CallbackListenerFactory = types_module.CallbackListenerFactory
CallbackListenerTimeoutError = types_module.CallbackListenerTimeoutError
CallbackParseError = types_module.CallbackParseError
CallbackPayload = types_module.CallbackPayload
CallbackStateMismatchError = types_module.CallbackStateMismatchError
ExchangeAuthorizationCode = types_module.ExchangeAuthorizationCode
InputText = types_module.InputText
LoginFlowDependencies = types_module.LoginFlowDependencies
Output = types_module.Output

EXPECTED_STATE = "expected-state"
CALLBACK_CODE = "callback-code"
MANUAL_CODE = "manual-code"
CALLBACK_TIMEOUT_SECONDS = 7
BIND_HOST = "0.0.0.0"  # noqa: S104
HTTP_OK = 200


def make_settings(*, host: str = BIND_HOST, host_uri: str = "localhost") -> OperatorSettings:
    """Build focused settings fixtures for the CLI auth flow."""
    return OperatorSettings(
        oauth=OAuthSettings(
            callback=CallbackSettings(
                host=host,
                port=1455,
                path="/auth/callback",
                host_uri=host_uri,
            )
        )
    )


def make_callback_url(*, code: str, state: str, settings: OperatorSettings) -> str:
    """Build a callback URL matching the configured redirect URI."""
    query = urlencode({"code": code, "state": state})
    return f"{settings.oauth.callback.redirect_uri()}?{query}"


def reserve_callback_port(*, host: str) -> int:
    """Reserve a free TCP port for the callback listener test."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener_socket:
        listener_socket.bind((host, 0))
        return listener_socket.getsockname()[1]


def send_callback_request(*, host: str, port: int, path: str, payload: CallbackPayload) -> int:
    """Send a real callback request to the local listener."""
    connection = http.client.HTTPConnection(host, port, timeout=2)
    try:
        callback_query = urlencode({"code": payload.code, "state": payload.state})
        connection.request("GET", f"{path}?{callback_query}")
        response = connection.getresponse()
        _ = response.read()
        return response.status
    finally:
        connection.close()


@final
class FakeListener:
    """Test callback listener with an injected result."""

    def __init__(self, result: CallbackPayload | Exception) -> None:
        """Store the callback result returned by the fake listener."""
        self._result = result
        self.closed = False
        self.timeout_seconds: int | None = None

    def wait_for_callback(self, *, timeout_seconds: int) -> CallbackPayload:
        """Return the injected callback payload or raise the injected error."""
        self.timeout_seconds = timeout_seconds
        if isinstance(self._result, Exception):
            raise self._result
        return self._result

    def close(self) -> None:
        """Record that the fake listener was closed."""
        self.closed = True


def make_listener_factory(listener: FakeListener) -> CallbackListenerFactory:
    """Return a typed listener factory for a fixed fake listener."""

    def listener_factory(*, host: str, port: int, path: str) -> FakeListener:
        del host, port, path
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


def exchange_success(*, code: str, code_verifier: str, redirect_uri: str) -> OpenAITokenResponse:
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
    """Build a manual callback input function with the expected state."""

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
    """Raise the focused re-login error surfaced by the core OAuth layer."""
    del code, code_verifier, redirect_uri
    message = "needs re-login"
    raise OpenAIOAuthReauthRequiredError(message)


def exchange_missing_account(
    *, code: str, code_verifier: str, redirect_uri: str
) -> OpenAITokenResponse:
    """Return a successful token exchange without an account claim."""
    del code, code_verifier, redirect_uri
    return make_token_response(account_id=None)


def unexpected_input(_prompt: str) -> str:
    """Fail fast when a test unexpectedly enters manual mode."""
    message = f"unexpected prompt: {_prompt}"
    raise AssertionError(message)


def test_run_openai_login_uses_settings_for_listener_binding_and_redirect_uri(tmp_path) -> None:
    """Login binds the listener to `host` and generates redirects from `host_uri`."""
    auth_main = load_auth_main()
    settings = make_settings(host=BIND_HOST, host_uri="127.0.0.1")
    store = OpenAIOAuthStore(path=tmp_path / "openai.json")
    listener = FakeListener(CallbackPayload(code=CALLBACK_CODE, state=EXPECTED_STATE))
    output_lines: list[str] = []
    seen_bind_hosts: list[str] = []
    seen_urls: list[str] = []

    def listener_factory(*, host: str, port: int, path: str) -> FakeListener:
        seen_bind_hosts.append(host)
        assert port == settings.oauth.callback.port
        assert path == settings.oauth.callback.path
        return listener

    def browser_open(url: str) -> bool:
        seen_urls.append(url)
        return True

    result = auth_main.run_openai_login(
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
    redirect_uri = parse_qs(urlsplit(seen_urls[0]).query)["redirect_uri"][0]

    assert result == 0
    assert credentials is not None
    assert credentials.account_id == EXPECTED_ACCOUNT_ID
    assert seen_bind_hosts == [settings.oauth.callback.host]
    assert redirect_uri == settings.oauth.callback.redirect_uri()
    assert urlsplit(redirect_uri).hostname == settings.oauth.callback.host_uri


def test_run_openai_login_persists_credentials_from_localhost_callback(tmp_path) -> None:
    """Successful login stores exchanged credentials and closes the listener."""
    auth_main = load_auth_main()
    settings = make_settings()
    store = OpenAIOAuthStore(path=tmp_path / "openai.json")
    listener = FakeListener(CallbackPayload(code=CALLBACK_CODE, state=EXPECTED_STATE))
    output_lines: list[str] = []

    result = auth_main.run_openai_login(
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
    assert credentials is not None
    assert credentials.access_token == ACCESS_TOKEN
    assert credentials.account_id == EXPECTED_ACCOUNT_ID
    assert listener.closed is True
    assert "complete" in "\n".join(output_lines).lower()


def test_run_openai_login_port_in_use_falls_back_to_manual_mode(tmp_path) -> None:
    """Port conflicts skip the listener and prompt for manual callback entry."""
    auth_main = load_auth_main()
    settings = make_settings()
    store = OpenAIOAuthStore(path=tmp_path / "openai.json")
    output_lines: list[str] = []

    def listener_factory(*, host: str, port: int, path: str) -> FakeListener:
        del host, port, path
        raise OSError(98, "Address already in use")

    result = auth_main.run_openai_login(
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
    assert store.load() is not None
    assert "manual" in "\n".join(output_lines).lower()


def test_run_openai_login_browser_failure_falls_back_to_manual_mode(tmp_path) -> None:
    """Browser launch failures fall back to manual callback entry."""
    auth_main = load_auth_main()
    settings = make_settings()
    store = OpenAIOAuthStore(path=tmp_path / "openai.json")
    listener = FakeListener(CallbackPayload(code="unused", state=EXPECTED_STATE))
    output_lines: list[str] = []

    result = auth_main.run_openai_login(
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
    assert store.load() is not None
    assert listener.closed is True
    assert "browser" in "\n".join(output_lines).lower()


def test_run_openai_login_timeout_falls_back_to_manual_mode(tmp_path) -> None:
    """Listener timeouts fall back to manual callback entry."""
    auth_main = load_auth_main()
    settings = make_settings()
    store = OpenAIOAuthStore(path=tmp_path / "openai.json")
    listener = FakeListener(CallbackListenerTimeoutError("timed out"))
    output_lines: list[str] = []

    result = auth_main.run_openai_login(
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
    assert store.load() is not None
    assert listener.closed is True
    assert listener.timeout_seconds == CALLBACK_TIMEOUT_SECONDS
    assert "manual" in "\n".join(output_lines).lower()


@pytest.mark.parametrize(
    ("listener_payload", "manual_state", "expected_message"),
    [
        pytest.param(
            CallbackPayload(code=CALLBACK_CODE, state="wrong-state"),
            None,
            "state mismatch",
            id="listener-mismatch",
        ),
        pytest.param(None, "wrong-state", "state mismatch", id="manual-mismatch"),
        pytest.param(None, None, "invalid openai callback input", id="invalid-manual-url"),
    ],
)
def test_run_openai_login_rejects_invalid_callback_input_without_persisting(
    tmp_path,
    listener_payload: CallbackPayload | None,
    manual_state: str | None,
    expected_message: str,
) -> None:
    """Invalid callback payloads fail cleanly without storing credentials."""
    auth_main = load_auth_main()
    settings = make_settings()
    store = OpenAIOAuthStore(path=tmp_path / "openai.json")
    output_lines: list[str] = []

    if listener_payload is not None:

        def listener_factory(*, host: str, port: int, path: str) -> FakeListener:
            del host, port, path
            return FakeListener(listener_payload)

        browser_open = browser_opens
        input_text = unexpected_input
    else:

        def listener_factory(*, host: str, port: int, path: str) -> FakeListener:
            del host, port, path
            raise OSError(98, "Address already in use")

        browser_open = unexpected_browser_open

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

    result = auth_main.run_openai_login(
        store=store,
        settings=settings,
        dependencies=make_login_dependencies(
            listener_factory=listener_factory,
            browser_open=browser_open,
            exchange_code=exchange_success,
            input_text=input_text,
            output=output_lines.append,
        ),
    )

    assert result == 1
    assert store.load() is None
    assert expected_message in "\n".join(output_lines).lower()


def test_parse_callback_url_and_state_validation_reject_invalid_values() -> None:
    """Callback parsing and state validation fail with focused errors."""
    openai_oauth = load_openai_oauth()
    settings = make_settings()

    payload = openai_oauth.parse_callback_url(
        make_callback_url(code=CALLBACK_CODE, state=EXPECTED_STATE, settings=settings),
        callback=settings.oauth.callback,
    )

    assert payload == CallbackPayload(code=CALLBACK_CODE, state=EXPECTED_STATE)

    with pytest.raises(CallbackParseError, match="callback URL path must be"):
        _ = openai_oauth.parse_callback_url(
            "http://localhost:1455/wrong-path?code=x&state=y", callback=settings.oauth.callback
        )

    with pytest.raises(CallbackStateMismatchError):
        _ = openai_oauth.validate_callback_payload(payload, pending_state="wrong-state")


def test_callback_listener_keeps_first_valid_payload() -> None:
    """The listener keeps the first valid callback payload it receives."""
    openai_oauth = load_openai_oauth()
    callback_host = "127.0.0.1"
    settings = make_settings(host=callback_host)
    callback_path = settings.oauth.callback.path
    callback_port = reserve_callback_port(host=callback_host)
    listener = openai_oauth.create_callback_listener(
        host=callback_host,
        port=callback_port,
        path=callback_path,
    )
    first_payload = CallbackPayload(code="first-code", state="first-state")
    second_payload = CallbackPayload(code="second-code", state="second-state")

    try:
        assert (
            send_callback_request(
                host=callback_host,
                port=callback_port,
                path=callback_path,
                payload=first_payload,
            )
            == HTTP_OK
        )
        assert (
            send_callback_request(
                host=callback_host,
                port=callback_port,
                path=callback_path,
                payload=second_payload,
            )
            == HTTP_OK
        )
        assert listener.wait_for_callback(timeout_seconds=1) == first_payload
    finally:
        listener.close()


def test_run_openai_login_surfaces_relogin_guidance_without_persisting(tmp_path) -> None:
    """Token exchange auth failures return guidance instead of storing partial state."""
    auth_main = load_auth_main()
    settings = make_settings()
    store = OpenAIOAuthStore(path=tmp_path / "openai.json")
    output_lines: list[str] = []
    listener = FakeListener(CallbackPayload(code=CALLBACK_CODE, state=EXPECTED_STATE))

    result = auth_main.run_openai_login(
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


def test_run_openai_login_tolerates_missing_account_claims(tmp_path) -> None:
    """Login still persists credentials when the token lacks a ChatGPT account claim."""
    auth_main = load_auth_main()
    settings = make_settings()
    store = OpenAIOAuthStore(path=tmp_path / "openai.json")
    listener = FakeListener(CallbackPayload(code=CALLBACK_CODE, state=EXPECTED_STATE))

    result = auth_main.run_openai_login(
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
    assert credentials is not None
    assert credentials.account_id is None

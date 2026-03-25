import base64
import json
from typing import final
from urllib.parse import parse_qs, urlencode, urlsplit

import pytest

from operator_cli.openai_auth import (
    BrowserOpen,
    CallbackListenerFactory,
    CallbackListenerTimeoutError,
    CallbackParseError,
    CallbackPayload,
    CallbackStateMismatchError,
    ExchangeAuthorizationCode,
    InputText,
    LoginFlowDependencies,
    Output,
    build_openai_oauth_provider,
    parse_callback_url,
    run_openai_login,
    run_openai_logout,
    run_openai_status,
    validate_callback_payload,
)
from operator_core.agent import OpenAIOAuthModelProvider
from operator_core.openai_oauth import (
    OpenAIOAuthCredentials,
    OpenAIOAuthReauthRequiredError,
    OpenAITokenResponse,
)
from operator_core.openai_store import OpenAIOAuthStore
from operator_shared.settings import CallbackSettings, OAuthSettings, OperatorSettings

EXPECTED_ACCOUNT_ID = "acct_123"
EXPECTED_STATE = "expected-state"
CALLBACK_CODE = "callback-code"
MANUAL_CODE = "manual-code"
ACCESS_TOKEN = "oauth-access-token"  # noqa: S105
REFRESH_TOKEN = "oauth-refresh-token"  # noqa: S105
CALLBACK_TIMEOUT_SECONDS = 7
BIND_HOST = "0.0.0.0"  # noqa: S104


def make_jwt(payload: dict[str, object]) -> str:
    """Build a minimal unsigned JWT fixture."""

    def encode(part: dict[str, object]) -> str:
        raw = json.dumps(part, separators=(",", ":")).encode()
        return base64.urlsafe_b64encode(raw).decode().rstrip("=")

    return ".".join((encode({"alg": "none", "typ": "JWT"}), encode(payload), "sig"))


def make_token_response(*, account_id: str | None = EXPECTED_ACCOUNT_ID) -> OpenAITokenResponse:
    """Create a successful OAuth token response fixture."""
    id_token_payload: dict[str, object] = {"sub": "user_123"}
    if account_id is not None:
        id_token_payload["chatgpt_account_id"] = account_id
    return OpenAITokenResponse(
        access_token=ACCESS_TOKEN,
        refresh_token=REFRESH_TOKEN,
        id_token=make_jwt(id_token_payload),
        expires_in=60,
        scope="openid profile email offline_access",
        token_type="Bearer",  # noqa: S106
    )


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
    settings = make_settings(host=BIND_HOST, host_uri="127.0.0.1")
    store = OpenAIOAuthStore(path=tmp_path / "openai.json")
    listener = FakeListener(CallbackPayload(code=CALLBACK_CODE, state=EXPECTED_STATE))
    output_lines: list[str] = []
    seen_bind_hosts: list[str] = []
    seen_urls: list[str] = []

    def listener_factory(*, host: str, port: int, path: str):
        seen_bind_hosts.append(host)
        assert port == settings.oauth.callback.port
        assert path == settings.oauth.callback.path
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
    redirect_uri = parse_qs(urlsplit(seen_urls[0]).query)["redirect_uri"][0]

    assert result == 0
    assert credentials is not None
    assert credentials.account_id == EXPECTED_ACCOUNT_ID
    assert seen_bind_hosts == [settings.oauth.callback.host]
    assert redirect_uri == settings.oauth.callback.redirect_uri()
    assert urlsplit(redirect_uri).hostname == settings.oauth.callback.host_uri


def test_run_openai_login_persists_credentials_from_localhost_callback(tmp_path) -> None:
    """Successful login stores exchanged credentials and closes the listener."""
    settings = make_settings()
    store = OpenAIOAuthStore(path=tmp_path / "openai.json")
    listener = FakeListener(CallbackPayload(code=CALLBACK_CODE, state=EXPECTED_STATE))
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
    assert credentials is not None
    assert credentials.access_token == ACCESS_TOKEN
    assert credentials.account_id == EXPECTED_ACCOUNT_ID
    assert listener.closed is True
    assert "complete" in "\n".join(output_lines).lower()


def test_run_openai_login_port_in_use_falls_back_to_manual_mode(tmp_path) -> None:
    """Port conflicts skip the listener and prompt for manual callback entry."""
    settings = make_settings()
    store = OpenAIOAuthStore(path=tmp_path / "openai.json")
    output_lines: list[str] = []

    def listener_factory(*, host: str, port: int, path: str):
        del host, port, path
        raise OSError(98, "Address already in use")

    result = run_openai_login(
        store=store,
        settings=settings,
        dependencies=make_login_dependencies(
            listener_factory=listener_factory,
            browser_open=lambda _url: pytest.fail("browser should not open"),
            exchange_code=exchange_success,
            input_text=lambda _prompt: make_callback_url(
                code=MANUAL_CODE,
                state=EXPECTED_STATE,
                settings=settings,
            ),
            output=output_lines.append,
        ),
    )

    assert result == 0
    assert store.load() is not None
    assert "manual" in "\n".join(output_lines).lower()


def test_run_openai_login_browser_failure_falls_back_to_manual_mode(tmp_path) -> None:
    """Browser launch failures fall back to manual callback entry."""
    settings = make_settings()
    store = OpenAIOAuthStore(path=tmp_path / "openai.json")
    listener = FakeListener(CallbackPayload(code="unused", state=EXPECTED_STATE))
    output_lines: list[str] = []

    result = run_openai_login(
        store=store,
        settings=settings,
        dependencies=make_login_dependencies(
            listener_factory=make_listener_factory(listener),
            browser_open=lambda _url: False,
            exchange_code=exchange_success,
            input_text=lambda _prompt: make_callback_url(
                code=MANUAL_CODE,
                state=EXPECTED_STATE,
                settings=settings,
            ),
            output=output_lines.append,
        ),
    )

    assert result == 0
    assert store.load() is not None
    assert listener.closed is True
    assert "browser" in "\n".join(output_lines).lower()


def test_run_openai_login_timeout_falls_back_to_manual_mode(tmp_path) -> None:
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
            input_text=lambda _prompt: make_callback_url(
                code=MANUAL_CODE,
                state=EXPECTED_STATE,
                settings=settings,
            ),
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

        def browser_open(_url: str) -> bool:
            pytest.fail("browser should not open")

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
    settings = make_settings()

    payload = parse_callback_url(
        make_callback_url(code=CALLBACK_CODE, state=EXPECTED_STATE, settings=settings),
        callback=settings.oauth.callback,
    )

    assert payload == CallbackPayload(code=CALLBACK_CODE, state=EXPECTED_STATE)

    with pytest.raises(CallbackParseError, match="callback URL path must be"):
        _ = parse_callback_url(
            "http://localhost:1455/wrong-path?code=x&state=y", callback=settings.oauth.callback
        )

    with pytest.raises(CallbackStateMismatchError):
        _ = validate_callback_payload(payload, pending_state="wrong-state")


def test_run_openai_login_surfaces_relogin_guidance_without_persisting(tmp_path) -> None:
    """Token exchange auth failures return guidance instead of storing partial state."""
    settings = make_settings()
    store = OpenAIOAuthStore(path=tmp_path / "openai.json")
    output_lines: list[str] = []
    listener = FakeListener(CallbackPayload(code=CALLBACK_CODE, state=EXPECTED_STATE))

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


def test_run_openai_login_tolerates_missing_account_claims(tmp_path) -> None:
    """Login still persists credentials when the token lacks a ChatGPT account claim."""
    settings = make_settings()
    store = OpenAIOAuthStore(path=tmp_path / "openai.json")
    listener = FakeListener(CallbackPayload(code=CALLBACK_CODE, state=EXPECTED_STATE))

    result = run_openai_login(
        store=store,
        settings=settings,
        dependencies=make_login_dependencies(
            listener_factory=make_listener_factory(listener),
            browser_open=browser_opens,
            exchange_code=exchange_missing_account,
            input_text=unexpected_input,
            output=lambda _line: None,
        ),
    )

    credentials = store.load()

    assert result == 0
    assert credentials is not None
    assert credentials.account_id is None


def test_run_openai_logout_and_status_use_core_store_boundary(tmp_path) -> None:
    """Logout and status stay thin wrappers over the core store model."""
    store = OpenAIOAuthStore(path=tmp_path / "openai.json")
    output_lines: list[str] = []
    _ = store.save(
        OpenAIOAuthCredentials(
            access_token=ACCESS_TOKEN,
            refresh_token=REFRESH_TOKEN,
            id_token=make_jwt({"chatgpt_account_id": EXPECTED_ACCOUNT_ID}),
            expires_at_ms=123_456,
            account_id=EXPECTED_ACCOUNT_ID,
            scope="openid profile email offline_access",
            token_type="Bearer",  # noqa: S106
        )
    )

    status_result = run_openai_status(store=store, output=output_lines.append)
    logout_result = run_openai_logout(store=store, output=output_lines.append)

    assert status_result == 0
    assert logout_result == 0
    assert store.load() is None
    assert EXPECTED_ACCOUNT_ID in "\n".join(output_lines)
    assert ACCESS_TOKEN not in "\n".join(output_lines)


def test_run_openai_status_reports_missing_and_present_credentials_without_secrets(
    tmp_path,
) -> None:
    """Status output reports login state and metadata while hiding tokens."""
    missing_store = OpenAIOAuthStore(path=tmp_path / "missing.json")
    missing_output: list[str] = []

    missing_result = run_openai_status(store=missing_store, output=missing_output.append)

    present_store = OpenAIOAuthStore(path=tmp_path / "present.json")
    _ = present_store.save(
        OpenAIOAuthCredentials(
            access_token=ACCESS_TOKEN,
            refresh_token=REFRESH_TOKEN,
            id_token=make_jwt({"chatgpt_account_id": EXPECTED_ACCOUNT_ID}),
            expires_at_ms=123_456,
            account_id=EXPECTED_ACCOUNT_ID,
            scope="openid profile email offline_access",
            token_type="Bearer",  # noqa: S106
        )
    )
    present_output: list[str] = []

    present_result = run_openai_status(store=present_store, output=present_output.append)
    rendered_present_output = "\n".join(present_output)

    assert missing_result == 0
    assert "not logged in" in "\n".join(missing_output).lower()
    assert present_result == 0
    assert EXPECTED_ACCOUNT_ID in rendered_present_output
    assert "expires" in rendered_present_output.lower()
    assert ACCESS_TOKEN not in rendered_present_output
    assert REFRESH_TOKEN not in rendered_present_output


def test_run_openai_logout_clears_missing_store_without_error(tmp_path) -> None:
    """Logout returns success even when no stored login is present."""
    output_lines: list[str] = []

    result = run_openai_logout(
        store=OpenAIOAuthStore(path=tmp_path / "missing.json"),
        output=output_lines.append,
    )

    assert result == 0
    assert "not found" in "\n".join(output_lines).lower()


def test_build_openai_oauth_provider_wraps_the_core_store(tmp_path) -> None:
    """CLI provider construction returns a usable OAuth-backed model provider."""
    store = OpenAIOAuthStore(path=tmp_path / "openai.json")

    provider = build_openai_oauth_provider(store=store)

    assert isinstance(provider, OpenAIOAuthModelProvider)
    assert provider.store is store

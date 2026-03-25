"""Public CLI orchestration helpers for OpenAI OAuth."""

import errno
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import final
from urllib.parse import urlsplit

from attrs import define, field

from operator_core.agent import OpenAIOAuthModelProvider
from operator_core.openai_oauth import (
    OpenAIOAuthReauthRequiredError,
    OpenAIOAuthStateMismatchError,
    build_authorize_url,
    build_pkce_verifier_and_challenge,
    exchange_authorization_code,
    generate_oauth_state,
    validate_oauth_state,
)
from operator_core.openai_store import OpenAIOAuthStore
from operator_shared.settings import CallbackSettings, OperatorSettings, load_operator_settings

from .errors import CallbackListenerTimeoutError, CallbackParseError, CallbackStateMismatchError
from .types import CallbackListener, CallbackPayload, LoginFlowDependencies, Output
from .utils import CALLBACK_TIMEOUT_MESSAGE, CALLBACK_TIMEOUT_SECONDS, format_expiry, open_browser
from .utils import parse_callback_query as _parse_callback_query
from .utils import parse_callback_url as _parse_callback_url


def run_openai_login(
    *,
    store: OpenAIOAuthStore | None = None,
    settings: OperatorSettings | None = None,
    dependencies: LoginFlowDependencies | None = None,
) -> int:
    """Run the OpenAI CLI login flow using core OAuth helpers and store APIs."""
    auth_store = OpenAIOAuthStore() if store is None else store
    operator_settings = load_operator_settings() if settings is None else settings
    login_dependencies = default_login_flow_dependencies() if dependencies is None else dependencies
    callback = operator_settings.oauth.callback
    redirect_uri = callback.redirect_uri()
    code_verifier, code_challenge = build_pkce_verifier_and_challenge()
    pending_state = login_dependencies.state_factory()
    authorize_url = build_authorize_url(
        state=pending_state,
        code_challenge=code_challenge,
        redirect_uri=redirect_uri,
    )

    try:
        callback_payload = _obtain_callback_payload(
            authorize_url=authorize_url,
            callback=callback,
            pending_state=pending_state,
            dependencies=login_dependencies,
        )
    except CallbackStateMismatchError:
        login_dependencies.output("OpenAI callback state mismatch. Please restart login.")
        return 1
    except CallbackParseError as error:
        login_dependencies.output(f"Invalid OpenAI callback input: {error}")
        return 1

    try:
        token_response = login_dependencies.exchange_code(
            code=callback_payload.code,
            code_verifier=code_verifier,
            redirect_uri=redirect_uri,
        )
    except OpenAIOAuthReauthRequiredError:
        login_dependencies.output("OpenAI login failed. Please log in again.")
        return 1

    _ = auth_store.save(token_response.to_credentials())
    login_dependencies.output("OpenAI login complete.")
    return 0


def run_openai_logout(*, store: OpenAIOAuthStore | None = None, output: Output = print) -> int:
    """Delete any stored OpenAI OAuth credentials."""
    auth_store = OpenAIOAuthStore() if store is None else store
    if auth_store.load() is None:
        output("OpenAI login not found.")
        auth_store.delete()
        return 0

    auth_store.delete()
    output("OpenAI login removed.")
    return 0


def run_openai_status(*, store: OpenAIOAuthStore | None = None, output: Output = print) -> int:
    """Report whether OpenAI OAuth credentials are stored."""
    auth_store = OpenAIOAuthStore() if store is None else store
    credentials = auth_store.load()
    if credentials is None:
        output("OpenAI status: not logged in.")
        return 0

    output("OpenAI status: logged in.")
    output(f"Account: {credentials.account_id or 'unknown'}")
    if credentials.expires_at_ms is None:
        output("Expires: unknown")
    else:
        output(f"Expires: {format_expiry(expires_at_ms=credentials.expires_at_ms)}")
        output(f"Expired: {'yes' if credentials.is_expired() else 'no'}")
    return 0


def build_openai_oauth_provider(
    *,
    store: OpenAIOAuthStore | None = None,
) -> OpenAIOAuthModelProvider:
    """Build the core OAuth model provider from the shared auth store."""
    auth_store = OpenAIOAuthStore() if store is None else store
    return OpenAIOAuthModelProvider(store=auth_store)


def validate_callback_payload(payload: CallbackPayload, *, pending_state: str) -> CallbackPayload:
    """Validate that a callback payload matches the pending OAuth state."""
    try:
        _ = validate_oauth_state(received_state=payload.state, pending_state=pending_state)
    except OpenAIOAuthStateMismatchError as error:
        raise CallbackStateMismatchError(str(error)) from error
    return payload


def parse_callback_url(callback_url: str, *, callback: CallbackSettings) -> CallbackPayload:
    """Parse a pasted redirect URL into a callback payload."""
    return _parse_callback_url(callback_url=callback_url, callback=callback)


def create_callback_listener(*, host: str, port: int, path: str) -> CallbackListener:
    """Start the localhost callback listener used by the browser login flow."""
    return _LocalhostCallbackListener(host=host, port=port, path=path)


def default_login_flow_dependencies() -> LoginFlowDependencies:
    """Build the production dependency set for the OpenAI login flow."""
    return LoginFlowDependencies(
        listener_factory=create_callback_listener,
        browser_open=open_browser,
        exchange_code=exchange_authorization_code,
        input_text=input,
        output=print,
        state_factory=generate_oauth_state,
        timeout_seconds=CALLBACK_TIMEOUT_SECONDS,
    )


def _obtain_callback_payload(
    *,
    authorize_url: str,
    callback: CallbackSettings,
    pending_state: str,
    dependencies: LoginFlowDependencies,
) -> CallbackPayload:
    listener: CallbackListener | None = None
    try:
        try:
            listener = dependencies.listener_factory(
                host=callback.host,
                port=callback.port,
                path=callback.path,
            )
        except OSError as error:
            if error.errno == errno.EADDRINUSE:
                dependencies.output(
                    "OpenAI callback port is already in use; falling back to manual login."
                )
                return _prompt_for_manual_callback(
                    authorize_url=authorize_url,
                    callback=callback,
                    pending_state=pending_state,
                    dependencies=dependencies,
                )
            raise

        try:
            browser_started = dependencies.browser_open(authorize_url)
        except webbrowser.Error:
            browser_started = False

        if not browser_started:
            dependencies.output(
                "Unable to open a browser automatically; falling back to manual login."
            )
            listener.close()
            listener = None
            return _prompt_for_manual_callback(
                authorize_url=authorize_url,
                callback=callback,
                pending_state=pending_state,
                dependencies=dependencies,
            )

        try:
            payload = listener.wait_for_callback(timeout_seconds=dependencies.timeout_seconds)
        except CallbackListenerTimeoutError:
            dependencies.output(
                "Timed out waiting for the OpenAI callback; falling back to manual login."
            )
            listener.close()
            listener = None
            return _prompt_for_manual_callback(
                authorize_url=authorize_url,
                callback=callback,
                pending_state=pending_state,
                dependencies=dependencies,
            )

        return validate_callback_payload(payload, pending_state=pending_state)
    finally:
        if listener is not None:
            listener.close()


def _prompt_for_manual_callback(
    *,
    authorize_url: str,
    callback: CallbackSettings,
    pending_state: str,
    dependencies: LoginFlowDependencies,
) -> CallbackPayload:
    dependencies.output("Open this URL to continue OpenAI login:")
    dependencies.output(authorize_url)
    callback_url = dependencies.input_text("Paste the full callback URL: ")
    callback_payload = parse_callback_url(callback_url, callback=callback)
    return validate_callback_payload(callback_payload, pending_state=pending_state)


@define
class _ListenerState:
    payload: CallbackPayload | None = None
    payload_ready: threading.Event = field(factory=threading.Event)


@final
class _LocalhostCallbackListener:
    """Real localhost listener for OAuth browser redirects."""

    def __init__(self, *, host: str, port: int, path: str) -> None:
        self._state = _ListenerState()
        self._server = _CallbackHTTPServer(
            (host, port),
            _CallbackRequestHandler,
            listener=self,
            callback_path=path,
        )
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    def wait_for_callback(self, *, timeout_seconds: int) -> CallbackPayload:
        if not self._state.payload_ready.wait(timeout_seconds):
            raise CallbackListenerTimeoutError(CALLBACK_TIMEOUT_MESSAGE)
        payload = self._state.payload
        if payload is None:
            raise CallbackListenerTimeoutError(CALLBACK_TIMEOUT_MESSAGE)
        return payload

    def close(self) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=1)

    def set_payload(self, payload: CallbackPayload) -> None:
        self._state.payload = payload
        self._state.payload_ready.set()


@final
class _CallbackHTTPServer(HTTPServer):
    allow_reuse_address: bool = False

    def __init__(
        self,
        server_address: tuple[str, int],
        request_handler_class: type[BaseHTTPRequestHandler],
        *,
        listener: _LocalhostCallbackListener,
        callback_path: str,
    ) -> None:
        self.listener = listener
        self.callback_path = callback_path
        super().__init__(server_address, request_handler_class)


class _CallbackRequestHandler(BaseHTTPRequestHandler):
    """HTTP handler that captures the OAuth redirect callback."""

    def do_GET(self) -> None:
        parts = urlsplit(self.path)
        server = self.server
        if not isinstance(server, _CallbackHTTPServer):
            self.send_error(500)
            return

        if parts.path != server.callback_path:
            self.send_error(404)
            return

        try:
            payload = _parse_callback_query(query=parts.query)
        except CallbackParseError as error:
            self.send_error(400, str(error))
            return

        server.listener.set_payload(payload)
        body = b"OpenAI login received. You can close this window."
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        _ = self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        del format, args

"""OpenAI-specific OAuth flow helpers for the CLI auth package."""

import errno
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import TYPE_CHECKING, final
from urllib.parse import parse_qs, urlsplit

from attrs import define, field

from operator_core.providers.openai import (
    OpenAIOAuthStateMismatchError,
    exchange_authorization_code,
    generate_oauth_state,
    validate_oauth_state,
)

from .types import (
    CallbackListener,
    CallbackListenerTimeoutError,
    CallbackParseError,
    CallbackPayload,
    CallbackStateMismatchError,
    LoginFlowDependencies,
)

if TYPE_CHECKING:
    from operator_shared.settings import CallbackSettings

CALLBACK_TIMEOUT_SECONDS = 120
INVALID_CALLBACK_URL_MESSAGE = "expected a full callback URL"
MISSING_CALLBACK_CODE_MESSAGE = "callback URL is missing code"
MISSING_CALLBACK_STATE_MESSAGE = "callback URL is missing state"
CALLBACK_TIMEOUT_MESSAGE = "timed out waiting for OpenAI callback"


def validate_callback_payload(payload: CallbackPayload, *, pending_state: str) -> CallbackPayload:
    """Validate that a callback payload matches the pending OAuth state."""
    try:
        _ = validate_oauth_state(received_state=payload.state, pending_state=pending_state)
    except OpenAIOAuthStateMismatchError as error:
        raise CallbackStateMismatchError(str(error)) from error
    return payload


def parse_callback_url(callback_url: str, *, callback: CallbackSettings) -> CallbackPayload:
    """Parse a pasted redirect URL into a callback payload."""
    parts = urlsplit(callback_url.strip())
    if not parts.scheme or not parts.netloc:
        raise CallbackParseError(INVALID_CALLBACK_URL_MESSAGE)
    if parts.path != callback.path:
        message = f"callback URL path must be {callback.path}"
        raise CallbackParseError(message)
    return _parse_callback_query(query=parts.query)


def create_callback_listener(*, host: str, port: int, path: str) -> CallbackListener:
    """Start the localhost callback listener used by the browser login flow."""
    return _LocalhostCallbackListener(host=host, port=port, path=path)


def default_login_flow_dependencies() -> LoginFlowDependencies:
    """Build the production dependency set for the OpenAI login flow."""
    return LoginFlowDependencies(
        listener_factory=create_callback_listener,
        browser_open=_open_browser,
        exchange_code=exchange_authorization_code,
        input_text=input,
        output=print,
        state_factory=generate_oauth_state,
        timeout_seconds=CALLBACK_TIMEOUT_SECONDS,
    )


def obtain_callback_payload(
    *,
    authorize_url: str,
    callback: CallbackSettings,
    pending_state: str,
    dependencies: LoginFlowDependencies,
) -> CallbackPayload:
    """Obtain a validated callback payload via localhost or manual fallback."""
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


def _parse_callback_query(*, query: str) -> CallbackPayload:
    """Parse callback query parameters into a typed payload."""
    params = parse_qs(query, strict_parsing=True)
    code_values = params.get("code")
    state_values = params.get("state")
    if not code_values or not code_values[0]:
        raise CallbackParseError(MISSING_CALLBACK_CODE_MESSAGE)
    if not state_values or not state_values[0]:
        raise CallbackParseError(MISSING_CALLBACK_STATE_MESSAGE)
    return CallbackPayload(code=code_values[0], state=state_values[0])


def _open_browser(url: str) -> bool:
    """Open a browser for the given authorize URL."""
    return webbrowser.open(url, new=1, autoraise=True)


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

"""Localhost callback listener for the CLI OpenAI auth flow."""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Event, Lock, Thread
from typing import TYPE_CHECKING, Protocol, final, override
from urllib.parse import parse_qs, urlsplit

if TYPE_CHECKING:
    from types import TracebackType


from attrs import define, field

from .errors import CallbackListenerTimeoutError, CallbackParseError
from .types import CallbackListener, CallbackPayload

CALLBACK_TIMEOUT_MESSAGE = "timed out waiting for OpenAI callback"
MISSING_CALLBACK_CODE_MESSAGE = "callback URL is missing code"
MISSING_CALLBACK_STATE_MESSAGE = "callback URL is missing state"


def create_callback_listener(
    *,
    bind_host: str,
    port: int,
    path: str,
    pending_state: str,
) -> CallbackListener:
    """Start the localhost callback listener used by the browser login flow."""
    return _LocalhostCallbackListener(
        bind_host=bind_host,
        port=port,
        path=path,
        pending_state=pending_state,
    )


def parse_callback_query(*, query: str) -> CallbackPayload:
    """Parse callback query parameters into a typed payload."""
    try:
        params = parse_qs(query, strict_parsing=True)
    except ValueError as error:
        raise CallbackParseError(str(error)) from error
    code_values = params.get("code")
    state_values = params.get("state")
    if not code_values or not code_values[0]:
        raise CallbackParseError(MISSING_CALLBACK_CODE_MESSAGE)
    if not state_values or not state_values[0]:
        raise CallbackParseError(MISSING_CALLBACK_STATE_MESSAGE)
    return CallbackPayload(code=code_values[0], state=state_values[0])


class _PayloadLock(Protocol):
    def __enter__(self) -> object: ...
    def __exit__(
        self,
        type_: type[BaseException] | None,
        value: BaseException | None,
        traceback: TracebackType | None,
        /,
    ) -> None: ...


@define
class _ListenerState:
    payload: CallbackPayload | None = None
    payload_ready: Event = field(factory=Event)
    payload_lock: _PayloadLock = field(factory=Lock)


@final
class _LocalhostCallbackListener:
    """Real localhost listener for OAuth browser redirects."""

    def __init__(self, *, bind_host: str, port: int, path: str, pending_state: str) -> None:
        self._state = _ListenerState()
        self._server = _CallbackHTTPServer(
            (bind_host, port),
            _CallbackRequestHandler,
            listener=self,
            callback_path=path,
            pending_state=pending_state,
        )
        self._thread = Thread(target=self._server.serve_forever, daemon=True)
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
        with self._state.payload_lock:
            if self._state.payload_ready.is_set():
                return
            self._state.payload = payload
            self._state.payload_ready.set()


@final
class _CallbackHTTPServer(ThreadingHTTPServer):
    daemon_threads: bool = True
    allow_reuse_address: bool = True

    def __init__(
        self,
        server_address: tuple[str, int],
        request_handler_class: type[BaseHTTPRequestHandler],
        *,
        listener: _LocalhostCallbackListener,
        callback_path: str,
        pending_state: str,
    ) -> None:
        self.listener = listener
        self.callback_path = callback_path
        self.pending_state = pending_state
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
            payload = parse_callback_query(query=parts.query)
        except CallbackParseError as error:
            self.send_error(400, str(error))
            return

        if payload.state != server.pending_state:
            self.send_error(400, "callback URL state does not match pending login state")
            return

        server.listener.set_payload(payload)
        body = b"OpenAI login received. You can close this window."
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        _ = self.wfile.write(body)

    @override
    def log_message(self, format: str, *args: object) -> None:
        del format, args

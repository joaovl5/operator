"""OpenAI-specific OAuth flow helpers for the CLI auth package."""

import errno
import webbrowser
from typing import TYPE_CHECKING
from urllib.parse import urlsplit

from operator_core_olden.providers.openai import (
    OpenAIOAuthStateMismatchError,
    exchange_authorization_code,
    generate_oauth_state,
    validate_oauth_state,
)
from operator_shared.settings import DEFAULT_CALLBACK_BIND_HOST

if TYPE_CHECKING:
    from operator_shared.settings import CallbackSettings

    from .types import CallbackListener, CallbackPayload

from .errors import CallbackListenerTimeoutError, CallbackParseError, CallbackStateMismatchError
from .listener import create_callback_listener, parse_callback_query
from .types import LoginFlowDependencies

CALLBACK_TIMEOUT_SECONDS = 120
INVALID_CALLBACK_URL_MESSAGE = "expected a full callback URL"


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
    try:
        port = parts.port
    except ValueError as error:
        raise CallbackParseError(INVALID_CALLBACK_URL_MESSAGE) from error
    if (
        parts.scheme != "http"
        or parts.hostname != DEFAULT_CALLBACK_BIND_HOST
        or port != callback.port
    ):
        message = f"callback URL must use {callback.redirect_uri()}"
        raise CallbackParseError(message)
    if parts.path != callback.path:
        message = f"callback URL path must be {callback.path}"
        raise CallbackParseError(message)
    return parse_callback_query(query=parts.query)


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
                bind_host=DEFAULT_CALLBACK_BIND_HOST,
                port=callback.port,
                path=callback.path,
                pending_state=pending_state,
            )
        except OSError as error:
            if error.errno == errno.EADDRINUSE:
                dependencies.output(
                    "OpenAI callback port is already in use; falling back to manual login."
                )
            else:
                dependencies.output(
                    "Unable to start the OpenAI callback listener automatically; falling back to manual login."
                )
            return _prompt_for_manual_callback(
                authorize_url=authorize_url,
                callback=callback,
                pending_state=pending_state,
                dependencies=dependencies,
            )

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
        if listener:
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


def _open_browser(url: str) -> bool:
    """Open a browser for the given authorize URL."""
    return webbrowser.open(url, new=1, autoraise=True)

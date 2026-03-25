"""Shared helpers for the CLI OpenAI auth flow."""

import webbrowser
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from urllib.parse import parse_qs, urlsplit

from .errors import CallbackParseError
from .types import CallbackPayload

if TYPE_CHECKING:
    from operator_shared.settings import CallbackSettings


CALLBACK_TIMEOUT_SECONDS = 120
INVALID_CALLBACK_URL_MESSAGE = "expected a full callback URL"
MISSING_CALLBACK_CODE_MESSAGE = "callback URL is missing code"
MISSING_CALLBACK_STATE_MESSAGE = "callback URL is missing state"
CALLBACK_TIMEOUT_MESSAGE = "timed out waiting for OpenAI callback"


def parse_callback_url(*, callback_url: str, callback: CallbackSettings) -> CallbackPayload:
    """Parse a pasted redirect URL into a callback payload."""
    parts = urlsplit(callback_url.strip())
    if not parts.scheme or not parts.netloc:
        raise CallbackParseError(INVALID_CALLBACK_URL_MESSAGE)
    if parts.path != callback.path:
        message = f"callback URL path must be {callback.path}"
        raise CallbackParseError(message)
    return parse_callback_query(query=parts.query)


def parse_callback_query(*, query: str) -> CallbackPayload:
    """Parse callback query parameters into a typed payload."""
    params = parse_qs(query, strict_parsing=True)
    code_values = params.get("code")
    state_values = params.get("state")
    if not code_values or not code_values[0]:
        raise CallbackParseError(MISSING_CALLBACK_CODE_MESSAGE)
    if not state_values or not state_values[0]:
        raise CallbackParseError(MISSING_CALLBACK_STATE_MESSAGE)
    return CallbackPayload(code=code_values[0], state=state_values[0])


def format_expiry(*, expires_at_ms: int) -> str:
    """Format a stored credential expiry timestamp in ISO-8601 form."""
    timestamp = datetime.fromtimestamp(expires_at_ms / 1000, tz=UTC)
    return timestamp.isoformat()


def open_browser(url: str) -> bool:
    """Open a browser for the given authorize URL."""
    return webbrowser.open(url, new=1, autoraise=True)

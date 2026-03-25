"""Shared OpenAI OAuth constants and helpers."""

import base64
import json
from collections.abc import Mapping
from typing import Any

from operator_shared.settings.main import CallbackSettings

OPENAI_OAUTH_AUTHORIZE_ENDPOINT = "https://auth.openai.com/oauth/authorize"
OPENAI_OAUTH_TOKEN_ENDPOINT = "https://auth.openai.com/oauth/token"  # noqa: S105
OPENAI_OAUTH_SCOPE = "openid profile email offline_access"
OPENAI_OAUTH_CLIENT_ID = "app_EMoamEEZ73f0CkXaXp7hrann"
OPENAI_OAUTH_REDIRECT_URI = CallbackSettings().redirect_uri()
TOKEN_TYPE_BEARER = "Bearer"  # noqa: S105
STATE_MISMATCH_MESSAGE = "OpenAI callback state mismatch"
TOKEN_RESPONSE_MISSING_REFRESH_MESSAGE = "token response did not include a refresh token"  # noqa: S105
TOKEN_REQUEST_INVALID_JSON_MESSAGE = "token endpoint returned invalid JSON"  # noqa: S105
TOKEN_REQUEST_MISSING_FIELDS_MESSAGE = "token endpoint response is missing required fields"  # noqa: S105
RELOGIN_REQUIRED_MESSAGE = "OpenAI OAuth credentials require re-login"
AUTH_ERROR_CODES = frozenset({400, 401, 403})
AUTH_ERROR_NAMES = frozenset(
    {
        "access_denied",
        "consent_required",
        "expired_token",
        "invalid_grant",
        "login_required",
        "token_expired",
    }
)
ACCOUNT_ID_CLAIMS = (
    "chatgpt_account_id",
    "https://auth.openai.com/account_id",
    "https://api.openai.com/auth/account_id",
    "account_id",
)
_JWT_PART_COUNT = 3


def add_base64_padding(value: str) -> str:
    """Add JWT-safe base64 padding when needed."""
    return value + ("=" * (-len(value) % 4))


def decode_jwt_payload(token: str) -> Mapping[str, Any] | None:
    """Decode a JWT payload without verifying its signature."""
    parts = token.split(".")
    if len(parts) != _JWT_PART_COUNT:
        return None

    try:
        payload_bytes = base64.urlsafe_b64decode(add_base64_padding(parts[1]))
        payload = json.loads(payload_bytes)
    except ValueError:
        return None

    return payload if isinstance(payload, Mapping) else None


def extract_account_id_from_id_token(id_token: str | None) -> str | None:
    """Extract the preferred ChatGPT account identifier from an ID token."""
    if not id_token:
        return None

    payload = decode_jwt_payload(id_token)
    if not isinstance(payload, Mapping):
        return None

    for claim_name in ACCOUNT_ID_CLAIMS:
        claim_value = payload.get(claim_name)
        if isinstance(claim_value, str) and claim_value.strip():
            return claim_value

    return None


def urlsafe_b64(raw: bytes) -> str:
    """Encode bytes as URL-safe base64 without padding."""
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")

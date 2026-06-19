"""Shared test helpers for the CLI auth package."""

import base64
import json

from operator_core.providers.openai import OpenAITokenResponse

EXPECTED_ACCOUNT_ID = "acct_123"
ACCESS_TOKEN = "oauth-access-token"  # noqa: S105
REFRESH_TOKEN = "oauth-refresh-token"  # noqa: S105


def make_jwt(payload: dict[str, object]) -> str:
    """Build a minimal unsigned JWT fixture."""

    def encode(part: dict[str, object]) -> str:
        raw = json.dumps(part, separators=(",", ":")).encode()
        return base64.urlsafe_b64encode(raw).decode().rstrip("=")

    return ".".join((encode({"alg": "none", "typ": "JWT"}), encode(payload), "sig"))


def make_token_response(*, account_id: str | None = EXPECTED_ACCOUNT_ID) -> OpenAITokenResponse:
    """Create a successful OAuth token response fixture."""
    id_token_payload: dict[str, object] = {"sub": "user_123"}
    if account_id  :
        id_token_payload["chatgpt_account_id"] = account_id
    return OpenAITokenResponse(
        access_token=ACCESS_TOKEN,
        refresh_token=REFRESH_TOKEN,
        id_token=make_jwt(id_token_payload),
        expires_in=60,
        scope="openid profile email offline_access",
        token_type="Bearer",  # noqa: S106
    )

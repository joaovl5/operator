import base64
import json
from typing import TYPE_CHECKING
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from pydantic import ValidationError

from operator_core_olden.providers.openai.errors import (
  OpenAIOAuthProtocolError,
  OpenAIOAuthReauthRequiredError,
  OpenAIOAuthStateMismatchError,
  OpenAIOAuthStoreCorruptionError,
)
from operator_core_olden.providers.openai.oauth.jwt import (
  extract_account_id_from_id_token,
)
from operator_core_olden.providers.openai.oauth.protocol import (
  OPENAI_OAUTH_AUTHORIZE_ENDPOINT,
  OPENAI_OAUTH_REDIRECT_URI,
  build_authorize_url,
  build_pkce_verifier_and_challenge,
  exchange_authorization_code,
  generate_oauth_state,
  refresh_access_token,
  validate_oauth_state,
)
from operator_core_olden.providers.openai.oauth.store import (
  OpenAIOAuthStore,
)
from operator_core_olden.providers.openai.oauth.types import (
  OPENAI_OAUTH_CLIENT_ID,
  OPENAI_OAUTH_SCOPE,
  AuthorizeRequest,
  OpenAIOAuthCredentials,
  OpenAITokenResponse,
  RefreshTokenRequest,
  TokenExchangeRequest,
)

if TYPE_CHECKING:
  from collections.abc import Callable
  from pathlib import Path

ACCESS_TOKEN = "oauth-access-token"  # noqa: S105
REFRESH_TOKEN = "oauth-refresh-token"  # noqa: S105
CODE = "oauth-code"
CODE_VERIFIER = "oauth-verifier"
STATE = "oauth-state"
CODE_CHALLENGE = "oauth-challenge"
EXPECTED_EXPIRES_AT_MS = 62_000


def make_jwt(payload: dict[str, object]) -> str:
  """Build a minimal unsigned JWT fixture."""

  def encode(part: dict[str, object]) -> str:
    raw = json.dumps(part, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")

  return ".".join(
    (encode({"alg": "none", "typ": "JWT"}), encode(payload), "sig")
  )


def test_store_constructor_derives_default_and_base_dir_paths(
  monkeypatch: pytest.MonkeyPatch,
  tmp_path: Path,
) -> None:
  """Store construction derives the expected credential and lock
  paths."""
  monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg"))

  default_store = OpenAIOAuthStore()
  base_dir_store = OpenAIOAuthStore(base_dir=tmp_path / "base")

  assert (
    default_store.path
    == tmp_path / "xdg" / "operator" / "auth" / "openai.json"
  )
  assert (
    default_store.lock_path
    == tmp_path / "xdg" / "operator" / "auth" / "openai.json.lock"
  )
  assert (
    base_dir_store.path == tmp_path / "base" / "auth" / "openai.json"
  )
  assert (
    base_dir_store.lock_path
    == tmp_path / "base" / "auth" / "openai.json.lock"
  )


def test_store_public_apis_surface_openai_corruption_error(
  tmp_path: Path,
) -> None:
  """Malformed on-disk payloads raise the OpenAI-specific
  corruption error."""
  path = tmp_path / "openai.json"
  _ = path.write_text("{not-json", encoding="utf-8")
  store = OpenAIOAuthStore(path=path)

  with pytest.raises(OpenAIOAuthStoreCorruptionError):
    _ = store.load()


def test_authorize_request_builds_expected_query_parameters() -> None:
  """Authorize URLs expose the expected query values after parsing."""
  request = AuthorizeRequest(
    state=STATE, code_challenge=CODE_CHALLENGE
  )

  url = request.authorize_url()

  parsed = urlsplit(url)
  assert parsed.scheme == "https"
  assert parsed.netloc == "auth.openai.com"
  assert parsed.path == "/oauth/authorize"
  assert parse_qs(parsed.query, strict_parsing=True) == {
    "response_type": ["code"],
    "client_id": [OPENAI_OAUTH_CLIENT_ID],
    "redirect_uri": [OPENAI_OAUTH_REDIRECT_URI],
    "scope": [OPENAI_OAUTH_SCOPE],
    "state": [STATE],
    "code_challenge": [CODE_CHALLENGE],
    "code_challenge_method": ["S256"],
    "id_token_add_organizations": ["true"],
    "codex_cli_simplified_flow": ["true"],
  }
  assert (
    build_authorize_url(state=STATE, code_challenge=CODE_CHALLENGE)
    == url
  )

  verifier, challenge = build_pkce_verifier_and_challenge()

  assert verifier
  assert challenge


def test_extract_account_id_prefers_chatgpt_claim() -> None:
  """Account extraction prefers the ChatGPT-specific claim when
  both exist."""
  token = make_jwt(
    {"account_id": "acct-fallback", "chatgpt_account_id": "acct-123"}
  )

  assert extract_account_id_from_id_token(token) == "acct-123"


def test_oauth_request_models_validate_required_fields() -> None:
  """OAuth request payloads are validated as typed models."""
  authorize_request = AuthorizeRequest(
    state=STATE, code_challenge=CODE_CHALLENGE
  )
  token_request = TokenExchangeRequest(
    code=CODE, code_verifier=CODE_VERIFIER
  )
  refresh_request = RefreshTokenRequest(refresh_token=REFRESH_TOKEN)

  assert authorize_request.client_id == OPENAI_OAUTH_CLIENT_ID
  assert token_request.redirect_uri == OPENAI_OAUTH_REDIRECT_URI
  assert refresh_request.client_id == OPENAI_OAUTH_CLIENT_ID

  with pytest.raises(ValidationError, match="state"):
    _ = AuthorizeRequest.model_validate(
      {"code_challenge": CODE_CHALLENGE}
    )
  with pytest.raises(ValidationError, match="code"):
    _ = TokenExchangeRequest.model_validate(
      {"code_verifier": CODE_VERIFIER}
    )
  with pytest.raises(ValidationError, match="refresh_token"):
    _ = RefreshTokenRequest.model_validate({})


def test_credentials_helpers_report_expiration_boundaries() -> None:
  """Credential helpers report expiry and buffer boundaries
  consistently."""
  credentials = OpenAIOAuthCredentials(
    access_token=ACCESS_TOKEN,
    refresh_token=REFRESH_TOKEN,
    expires_at_ms=2_000,
  )

  assert credentials.is_expired(now_ms=1_999) is False
  assert credentials.is_expired(now_ms=2_000) is True
  assert (
    credentials.expires_within(now_ms=1_500, buffer_ms=499) is False
  )
  assert (
    credentials.expires_within(now_ms=1_500, buffer_ms=500) is True
  )


def test_openai_token_response_uses_shared_account_id_helper(
  monkeypatch: pytest.MonkeyPatch,
) -> None:
  """Token credential conversion delegates account extraction to
  the shared JWT helper."""
  seen_tokens: list[str | None] = []

  def fake_extract_account_id(id_token: str | None) -> str | None:
    seen_tokens.append(id_token)
    return "acct-123"

  monkeypatch.setattr(
    "operator_core.providers.openai.oauth.types.extract_account_id_from_id_token",
    fake_extract_account_id,
  )

  response = OpenAITokenResponse(
    access_token=ACCESS_TOKEN,
    refresh_token=REFRESH_TOKEN,
    id_token=make_jwt({"chatgpt_account_id": "acct-123"}),
    expires_in=60,
  )

  credentials = response.to_credentials(now_ms=2_000)

  assert credentials.account_id == "acct-123"
  assert seen_tokens == [response.id_token]


def test_generate_and_validate_oauth_state_use_public_helpers(
  monkeypatch: pytest.MonkeyPatch,
) -> None:
  """State helpers generate urlsafe entropy and reject mismatches."""
  seen_lengths: list[int] = []

  def fake_token_urlsafe(length: int) -> str:
    seen_lengths.append(length)
    return STATE

  monkeypatch.setattr(
    "operator_core.providers.openai.oauth.protocol.secrets.token_urlsafe",
    fake_token_urlsafe,
  )

  assert generate_oauth_state() == STATE
  assert (
    validate_oauth_state(received_state=STATE, pending_state=STATE)
    == STATE
  )
  assert seen_lengths == [32]

  with pytest.raises(OpenAIOAuthStateMismatchError):
    _ = validate_oauth_state(
      received_state="wrong-state", pending_state=STATE
    )


def generate_with_client(client: httpx.Client) -> OpenAITokenResponse:
  """Exchange an authorization code using the provided HTTP client."""
  return exchange_authorization_code(
    code=CODE,
    code_verifier=CODE_VERIFIER,
    client=client,
  )


def refresh_with_client(client: httpx.Client) -> OpenAITokenResponse:
  """Refresh an access token using the provided HTTP client."""
  return refresh_access_token(
    refresh_token=REFRESH_TOKEN,
    client=client,
  )


@pytest.mark.parametrize(
  ("operation", "expected_body"),
  [
    pytest.param(
      generate_with_client,
      {
        "grant_type": ["authorization_code"],
        "code": [CODE],
        "code_verifier": [CODE_VERIFIER],
        "client_id": [OPENAI_OAUTH_CLIENT_ID],
        "redirect_uri": [OPENAI_OAUTH_REDIRECT_URI],
      },
      id="exchange",
    ),
    pytest.param(
      refresh_with_client,
      {
        "grant_type": ["refresh_token"],
        "refresh_token": [REFRESH_TOKEN],
        "client_id": [OPENAI_OAUTH_CLIENT_ID],
      },
      id="refresh",
    ),
  ],
)
def test_token_requests_use_httpx_form_posts(
  operation: Callable[[httpx.Client], OpenAITokenResponse],
  expected_body: dict[str, list[str]],
) -> None:
  """Token operations send form-encoded POST requests through
  httpx."""
  seen_requests: list[httpx.Request] = []

  def handler(request: httpx.Request) -> httpx.Response:
    seen_requests.append(request)
    return httpx.Response(
      200,
      json={
        "access_token": ACCESS_TOKEN,
        "refresh_token": REFRESH_TOKEN,
        "token_type": "Bearer",
      },
    )

  client = httpx.Client(transport=httpx.MockTransport(handler))

  response = operation(client)

  assert response.access_token == ACCESS_TOKEN
  assert response.refresh_token == REFRESH_TOKEN
  assert seen_requests
  request = seen_requests[0]
  assert request.method == "POST"
  assert str(request.url) == OPENAI_OAUTH_AUTHORIZE_ENDPOINT.replace(
    "authorize", "token"
  )
  assert request.headers["Content-Type"].startswith(
    "application/x-www-form-urlencoded"
  )
  assert (
    parse_qs(request.content.decode("utf-8"), strict_parsing=True)
    == expected_body
  )


def test_token_response_to_credentials_preserves_previous_refresh_token() -> (
  None
):
  """Token responses keep the existing refresh token when omitted."""
  previous = OpenAIOAuthCredentials(
    access_token="old-access-token",  # noqa: S106
    refresh_token=REFRESH_TOKEN,
    expires_at_ms=1_000,
  )
  response = OpenAITokenResponse(
    access_token=ACCESS_TOKEN, refresh_token=None, expires_in=60
  )

  credentials = response.to_credentials(
    now_ms=2_000, previous_credentials=previous
  )

  assert credentials.access_token == ACCESS_TOKEN
  assert credentials.refresh_token == REFRESH_TOKEN
  assert credentials.expires_at_ms == EXPECTED_EXPIRES_AT_MS


def test_token_response_to_credentials_preserves_previous_account_id_on_refresh_without_id_token() -> (
  None
):
  """Refresh responses preserve account_id when no new id_token is
  returned."""
  previous = OpenAIOAuthCredentials(
    access_token="old-access-token",  # noqa: S106
    refresh_token=REFRESH_TOKEN,
    account_id="acct-previous",
    expires_at_ms=1_000,
  )
  response = OpenAITokenResponse(
    access_token=ACCESS_TOKEN,
    refresh_token=REFRESH_TOKEN,
    expires_in=60,
  )

  credentials = response.to_credentials(
    now_ms=2_000, previous_credentials=previous
  )

  assert credentials.account_id == "acct-previous"
  assert credentials.refresh_token == REFRESH_TOKEN
  assert credentials.expires_at_ms == EXPECTED_EXPIRES_AT_MS


@pytest.mark.parametrize(
  "operation",
  [
    pytest.param(generate_with_client, id="exchange"),
    pytest.param(refresh_with_client, id="refresh"),
  ],
)
def test_token_operations_map_auth_failures_to_relogin_errors(
  operation: Callable[[httpx.Client], OpenAITokenResponse],
) -> None:
  """Focused auth failures surface as re-login errors for both
  token operations."""

  def handler(request: httpx.Request) -> httpx.Response:
    return httpx.Response(
      401, json={"error": "invalid_grant"}, request=request
    )

  client = httpx.Client(transport=httpx.MockTransport(handler))

  with pytest.raises(OpenAIOAuthReauthRequiredError):
    _ = operation(client)


@pytest.mark.parametrize(
  ("response", "match"),
  [
    pytest.param(
      httpx.Response(400, json={"error": "temporarily_unavailable"}),
      "status 400",
      id="non-auth-status",
    ),
    pytest.param(
      httpx.Response(401, json={"error": "unauthorized"}),
      "status 401",
      id="generic-401",
    ),
    pytest.param(
      httpx.Response(200, text="not-json"),
      "valid JSON",
      id="invalid-json",
    ),
    pytest.param(
      httpx.Response(200, json={}),
      "required fields",
      id="missing-fields",
    ),
  ],
)
def test_exchange_authorization_code_surfaces_protocol_and_auth_failures(
  response: httpx.Response,
  match: str,
) -> None:
  """Code exchange keeps protocol failures distinct from re-login
  failures."""

  def handler(request: httpx.Request) -> httpx.Response:
    return httpx.Response(
      response.status_code,
      headers=response.headers,
      content=response.content,
      request=request,
    )

  client = httpx.Client(transport=httpx.MockTransport(handler))

  with pytest.raises(OpenAIOAuthProtocolError, match=match):
    _ = exchange_authorization_code(
      code=CODE,
      code_verifier=CODE_VERIFIER,
      client=client,
    )

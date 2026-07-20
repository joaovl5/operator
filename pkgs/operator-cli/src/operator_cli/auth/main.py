"""Public CLI orchestration helpers for OpenAI OAuth."""

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from operator_core_olden.providers.openai import (
  OpenAIOAuthProtocolError,
  OpenAIOAuthReauthRequiredError,
  OpenAIOAuthStore,
  OpenAIOAuthStoreError,
  build_authorize_url,
  build_pkce_verifier_and_challenge,
)
from operator_core_olden.providers.utils.store.errors import (
  JsonCredentialStoreTransactionError,
)
from operator_shared.settings import (
  OperatorSettings,
  load_operator_settings,
)

from .errors import CallbackParseError, CallbackStateMismatchError
from .openai_oauth import (
  default_login_flow_dependencies,
  obtain_callback_payload,
)

if TYPE_CHECKING:
  from .types import LoginFlowDependencies, Output


def run_openai_login(
  *,
  store: OpenAIOAuthStore | None = None,
  settings: OperatorSettings | None = None,
  dependencies: LoginFlowDependencies | None = None,
) -> int:
  """Run the OpenAI CLI login flow using core OAuth helpers
  and store APIs.
  """
  auth_store = OpenAIOAuthStore() if store is None else store
  operator_settings = (
    load_operator_settings() if settings is None else settings
  )
  login_dependencies = (
    default_login_flow_dependencies()
    if dependencies is None
    else dependencies
  )
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
    callback_payload = obtain_callback_payload(
      authorize_url=authorize_url,
      callback=callback,
      pending_state=pending_state,
      dependencies=login_dependencies,
    )
  except CallbackStateMismatchError:
    login_dependencies.output(
      "OpenAI callback state mismatch. Please restart login."
    )
    return 1
  except CallbackParseError as error:
    login_dependencies.output(
      f"Invalid OpenAI callback input: {error}"
    )
    return 1

  try:
    token_response = login_dependencies.exchange_code(
      code=callback_payload.code,
      code_verifier=code_verifier,
      redirect_uri=redirect_uri,
    )
    credentials = token_response.to_credentials()
  except OpenAIOAuthReauthRequiredError:
    login_dependencies.output(
      "OpenAI login failed. Please log in again."
    )
    return 1
  except OpenAIOAuthProtocolError as error:
    login_dependencies.output(f"OpenAI login failed: {error}")
    return 1

  try:
    _ = auth_store.save(credentials)
  except (
    JsonCredentialStoreTransactionError,
    OSError,
    OpenAIOAuthStoreError,
  ) as error:
    login_dependencies.output(
      f"OpenAI login could not be saved: {error}"
    )
    return 1
  login_dependencies.output("OpenAI login complete.")
  return 0


def run_openai_logout(
  *, store: OpenAIOAuthStore | None = None, output: Output = print
) -> int:
  """Delete any stored OpenAI OAuth credentials."""
  auth_store = OpenAIOAuthStore() if store is None else store
  try:
    credentials = auth_store.load()
  except OpenAIOAuthStoreError as error:
    credentials = None
    output(
      f"Stored OpenAI login is unreadable; removing it. ({error})"
    )

  try:
    auth_store.delete()
  except (JsonCredentialStoreTransactionError, OSError) as error:
    output(f"OpenAI login could not be removed: {error}")
    return 1

  if credentials is None:
    output("OpenAI login not found.")
    return 0

  output("OpenAI login removed.")
  return 0


def run_openai_status(
  *, store: OpenAIOAuthStore | None = None, output: Output = print
) -> int:
  """Report whether OpenAI OAuth credentials are stored."""
  auth_store = OpenAIOAuthStore() if store is None else store
  try:
    credentials = auth_store.load()
  except OpenAIOAuthStoreError as error:
    output(f"OpenAI status could not read stored login: {error}")
    return 1
  if credentials is None:
    output("OpenAI status: not logged in.")
    return 0

  output("OpenAI status: logged in.")
  output(f"Account: {credentials.account_id or 'unknown'}")
  if credentials.expires_at_ms is None:
    output("Expires: unknown")
  else:
    output(
      "Expires: "
      f"{_format_expiry(expires_at_ms=credentials.expires_at_ms)}"
    )
    output(f"Expired: {'yes' if credentials.is_expired() else 'no'}")
  return 0


def _format_expiry(*, expires_at_ms: int) -> str:
  """Format a stored credential expiry timestamp in ISO-8601 form."""
  timestamp = datetime.fromtimestamp(expires_at_ms / 1000, tz=UTC)
  return timestamp.isoformat()

"""Public CLI orchestration helpers for OpenAI OAuth."""

from datetime import UTC, datetime

from operator_core.providers.openai import (
    OpenAIOAuthReauthRequiredError,
    OpenAIOAuthStore,
    build_authorize_url,
    build_pkce_verifier_and_challenge,
)
from operator_shared.settings import OperatorSettings, load_operator_settings

from .openai_oauth import default_login_flow_dependencies, obtain_callback_payload
from .types import CallbackParseError, CallbackStateMismatchError, LoginFlowDependencies, Output


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
        callback_payload = obtain_callback_payload(
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
        output(f"Expires: {_format_expiry(expires_at_ms=credentials.expires_at_ms)}")
        output(f"Expired: {'yes' if credentials.is_expired() else 'no'}")
    return 0


def _format_expiry(*, expires_at_ms: int) -> str:
    """Format a stored credential expiry timestamp in ISO-8601 form."""
    timestamp = datetime.fromtimestamp(expires_at_ms / 1000, tz=UTC)
    return timestamp.isoformat()

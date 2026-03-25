"""OpenAI OAuth CLI helpers."""

from operator_core.openai_oauth import generate_oauth_state, validate_oauth_state

from .errors import (
    CallbackListenerTimeoutError,
    CallbackParseError,
    CallbackStateMismatchError,
    OpenAIAuthCliError,
)
from .main import (
    build_openai_oauth_provider,
    create_callback_listener,
    default_login_flow_dependencies,
    parse_callback_url,
    run_openai_login,
    run_openai_logout,
    run_openai_status,
    validate_callback_payload,
)
from .types import (
    BrowserOpen,
    CallbackListener,
    CallbackListenerFactory,
    CallbackPayload,
    ExchangeAuthorizationCode,
    InputText,
    LoginFlowDependencies,
    Output,
    StateFactory,
)

__all__ = [
    "BrowserOpen",
    "CallbackListener",
    "CallbackListenerFactory",
    "CallbackListenerTimeoutError",
    "CallbackParseError",
    "CallbackPayload",
    "CallbackStateMismatchError",
    "ExchangeAuthorizationCode",
    "InputText",
    "LoginFlowDependencies",
    "OpenAIAuthCliError",
    "Output",
    "StateFactory",
    "build_openai_oauth_provider",
    "create_callback_listener",
    "default_login_flow_dependencies",
    "generate_oauth_state",
    "parse_callback_url",
    "run_openai_login",
    "run_openai_logout",
    "run_openai_status",
    "validate_callback_payload",
    "validate_oauth_state",
]

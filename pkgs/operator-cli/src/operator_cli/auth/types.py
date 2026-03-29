"""Types and errors for the CLI OpenAI auth flow."""

from collections.abc import Callable
from typing import TYPE_CHECKING, Protocol

from attrs import define

if TYPE_CHECKING:
    from operator_core.providers.openai import OpenAITokenResponse


class OpenAIAuthCliError(RuntimeError):
    """Base error for CLI-facing OpenAI auth failures."""


class CallbackParseError(ValueError, OpenAIAuthCliError):
    """Raised when a pasted callback URL cannot be parsed safely."""


class CallbackStateMismatchError(OpenAIAuthCliError):
    """Raised when an OAuth callback returns an unexpected state value."""


class CallbackListenerTimeoutError(TimeoutError, OpenAIAuthCliError):
    """Raised when no valid OAuth callback is received before the deadline."""


@define(frozen=True, kw_only=True)
class CallbackPayload:
    """Authorization-code callback values returned from the browser flow."""

    code: str
    state: str


class CallbackListener(Protocol):
    """Interface for obtaining an OpenAI OAuth callback payload."""

    def wait_for_callback(self, *, timeout_seconds: int) -> CallbackPayload:
        """Wait for a callback payload or raise when the wait expires."""
        ...

    def close(self) -> None:
        """Release any resources held by the callback listener."""
        ...


class CallbackListenerFactory(Protocol):
    """Factory for creating callback listeners bound to local settings."""

    def __call__(self, *, host: str, port: int, path: str) -> CallbackListener:
        """Create a listener bound to the configured callback host and port."""
        ...


class ExchangeAuthorizationCode(Protocol):
    """Typed authorization-code exchange hook used by the CLI flow."""

    def __call__(
        self,
        *,
        code: str,
        code_verifier: str,
        redirect_uri: str,
    ) -> OpenAITokenResponse:
        """Exchange an authorization code for OAuth tokens."""
        ...


type BrowserOpen = Callable[[str], bool]
type InputText = Callable[[str], str]
type Output = Callable[[str], None]
type StateFactory = Callable[[], str]


@define(frozen=True, kw_only=True)
class LoginFlowDependencies:
    """Injected side effects for the OpenAI CLI login flow."""

    listener_factory: CallbackListenerFactory
    browser_open: BrowserOpen
    exchange_code: ExchangeAuthorizationCode
    input_text: InputText
    output: Output
    state_factory: StateFactory
    timeout_seconds: int

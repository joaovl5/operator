"""Session-related errors."""


class SessionError(RuntimeError): ...


class SessionMissingAgentError(SessionError): ...

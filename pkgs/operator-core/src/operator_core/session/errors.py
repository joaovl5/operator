"""Session-related errors."""


class SessionError(RuntimeError): ...


class SessionAgentUnavailableError(SessionError): ...


class SessionMissingAgentError(SessionError): ...

class SessionPersistenceUnavailableError(SessionError): ...


# non-error exceptions (act as signals)

# both below are stubs/todo


class SessionRequiresCompaction(BaseException): ...


class SessionTurnsExhausted(BaseException): ...

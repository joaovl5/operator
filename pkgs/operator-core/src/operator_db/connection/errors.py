"""Database connection error hierarchy."""


class OperatorDbConnectionError(RuntimeError):
    """Base error for database connection helpers."""


class OperatorDbMigrationError(OperatorDbConnectionError):
    """Raised when database migration readiness cannot be established."""


__all__ = ["OperatorDbConnectionError", "OperatorDbMigrationError"]

"""Reusable JSON credential store errors."""


class JsonCredentialStoreError(RuntimeError):
    """Base JSON credential store error."""


class JsonCredentialStoreCorruptionError(JsonCredentialStoreError):
    """Raised when persisted credentials cannot be decoded."""


class JsonCredentialStoreTransactionError(JsonCredentialStoreError):
    """Raised when a transaction operation runs without the store lock."""

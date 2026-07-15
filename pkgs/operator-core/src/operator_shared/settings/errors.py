"""Errors raised while loading Operator settings."""


class OperatorSettingsError(RuntimeError):
  """Base error for shared Operator settings helpers."""


class OperatorSettingsLoadError(OperatorSettingsError):
  """Raised when `operator.toml` cannot be read or parsed."""

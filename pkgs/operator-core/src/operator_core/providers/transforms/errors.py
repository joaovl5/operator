"""Provider transform errors."""

from operator_core.providers.errors import ProviderError


class ProviderTransformError(ProviderError):
    """Base error for provider transform failures."""


class UnsupportedProviderMessageError(ProviderTransformError):
    """Provider message shape is not supported by the stable transform."""


__all__ = ["ProviderTransformError", "UnsupportedProviderMessageError"]

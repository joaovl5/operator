"""Z.AI OpenAI-compatible provider integration."""

from .client import ZAIModelProvider, get_zai_client
from .types import (
    ZAI_CODING_BASE_URL,
    ZAI_DEFAULT_MODEL,
    ZAI_GENERAL_BASE_URL,
    ZAIModelConfig,
    ZAIModelSettings,
)

__all__ = [
    "ZAI_CODING_BASE_URL",
    "ZAI_DEFAULT_MODEL",
    "ZAI_GENERAL_BASE_URL",
    "ZAIModelConfig",
    "ZAIModelProvider",
    "ZAIModelSettings",
    "get_zai_client",
]

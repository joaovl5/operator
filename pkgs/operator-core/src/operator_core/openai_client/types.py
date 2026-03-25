"""Types for the OpenAI client package."""

from collections.abc import Callable
from typing import ClassVar

from pydantic import BaseModel, ConfigDict

from operator_core.openai_oauth import OpenAITokenResponse


class OAuthResponsesSettings(BaseModel):
    """Serializable default settings for OAuth-backed Responses requests."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    openai_store: bool = False
    openai_send_reasoning_ids: bool = False


type RefreshAccessToken = Callable[[str], OpenAITokenResponse]

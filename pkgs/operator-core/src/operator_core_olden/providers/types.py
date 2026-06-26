"""Provider-agnostic configuration models."""

from typing import ClassVar

from pydantic import BaseModel, ConfigDict


class ModelSettings(BaseModel):
    """Serializable provider settings payload."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")


class ModelConfig[SettingsT: ModelSettings = ModelSettings](BaseModel):
    """Serializable provider model configuration."""

    name: str
    temperature: float = 0.1
    settings: SettingsT

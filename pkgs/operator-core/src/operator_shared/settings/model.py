from enum import StrEnum

from pydantic import BaseModel, Field, SecretStr

from operator_shared.settings.types import Entries, Fac, SettingsBase


class _ModelApiKeyEnv(BaseModel):
    """Use an env variable instead of putting in the config."""

    env: str


class _ModelApiURLKnownChoices(StrEnum):
    OPENAI = "openai"
    OPENROUTER = "openruter"
    GROQ = "groq"


class _ModelApiURLKnown(BaseModel):
    """Use an already-known API url."""

    known: _ModelApiURLKnownChoices


class _ModelProviderSettings(SettingsBase):
    key: str

    temperature: float | None = Field(None, ge=0, le=1)

    api_key: SecretStr | _ModelApiKeyEnv | None = None
    api_url: str | _ModelApiURLKnown | None = None


class ModelProvidersSettings(SettingsBase):
    """Settings for model providers.

    Providers are set as part of a key-value dictionary.
    """

    entries: Fac[Entries[_ModelProviderSettings]]

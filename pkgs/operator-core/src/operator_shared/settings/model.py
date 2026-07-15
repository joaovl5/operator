import os
from enum import StrEnum
from functools import cached_property
from typing import Self

from openai import AsyncOpenAI
from pydantic import Field, PositiveInt, SecretStr, model_validator
from pydantic_ai.providers import Provider
from pydantic_ai.providers.openai import OpenAIProvider

from operator_shared.settings.types import Entries, Fac, SettingsBase


class _TakesEnv(SettingsBase):
  """Use an env variable instead of putting in the config."""

  env: str


class _KnownAPI(StrEnum):
  OPENAI = "openai"
  OPENROUTER = "openrouter"
  GROQ = "groq"


_API_KNOWN_TO_URL: dict[_KnownAPI, str] = {
  _KnownAPI.OPENAI: "https://api.openai.com/v1",
  _KnownAPI.OPENROUTER: "https://openrouter.ai/api/v1",
  _KnownAPI.GROQ: "https://api.groq.com/openai/v1",
}


class _TakesAPIKnown(SettingsBase):
  """Use an already-known API url."""

  known: _KnownAPI


class _ProviderSettings(SettingsBase):
  key: str

  api_key: SecretStr | _TakesEnv | None = None
  api_url: str | _TakesAPIKnown | None = None

  @cached_property
  def comp_api_key(self) -> str | None:
    """Computed API key based on its variants."""
    match x := self.api_key:
      case None:
        return None
      case SecretStr():
        return x.get_secret_value()
      case _TakesEnv():
        return os.getenv(x.env)

  @cached_property
  def comp_api_url(self) -> str | None:
    """Computed API url based on its variants."""
    match x := self.api_url:
      case None:
        return None
      case str():
        return x
      case _TakesAPIKnown():
        return _API_KNOWN_TO_URL[x.known]

  def get_pydantic_ai_provider(self) -> Provider:
    """Get Pydantic AI provider instance."""
    return OpenAIProvider(
      openai_client=AsyncOpenAI(
        api_key=self.comp_api_key,
        base_url=self.comp_api_url,
      )
    )


class ProvidersSettings(SettingsBase):
  """Settings for model providers.

  Providers are set as part of a key-value dictionary.
  """

  entries: Fac[Entries[_ProviderSettings]]


class _ContextSettings(SettingsBase):
  upper_bound: PositiveInt | None = None
  """Provider-facing upper-bound for context length, in tokens.

    If `None`, will attempted to be resolved with heuristics later.
    """


class _ModelSettings(SettingsBase):
  key: str
  provider_key: str

  model_name: str

  is_default: bool = False
  temperature: float | None = Field(None, ge=0, le=1)

  context: Fac[_ContextSettings]


class ModelsSettings(SettingsBase):
  """Configures model presets.

  Models are set as part of a key-value dictionary.
  """

  entries: Fac[Entries[_ModelSettings]]

  @cached_property
  def default_entry_force(self) -> _ModelSettings:
    """Same as `.default_entry` but raises an error if is `None`."""
    if (x := self.default_entry) is None:
      msg = "No default model entry was found, cannot proceed without one."
      raise ValueError(msg)
    return x

  @cached_property
  def default_entry(self) -> _ModelSettings | None:
    """Default model entry, or `None` is no entries exist."""
    if len(self.entries) == 0:
      return None
    return [x for x in self.entries.values() if x.is_default].pop()

  @model_validator(mode="after")
  def _validate_entries(self) -> Self:
    default_key: str | None = None

    entries = list(self.entries.values())
    def_entries = [x for x in entries if x.is_default]
    match len(def_entries):
      case 0:
        default_key = entries.pop().key if len(entries) >= 1 else None
      case 1:
        default_key = def_entries.pop().key
      case _:
        msg = (
          "More than one entries have `is_default` set to True! "
          "Entry keys that have `is_default` are: "
          f"{', '.join(x.key for x in def_entries)}"
        )
        raise ValueError(msg)
    if default_key:
      self.entries[default_key].is_default = True

    return self

"""Shared Operator settings models and loaders."""

from typing import Self

from pydantic import model_validator

from .agent import AgentsSettings
from .database import DatabaseSettings
from .model import ModelsSettings, ProvidersSettings, _ModelSettings
from .oauth import OAuthSettings
from .types import Fac, SettingsBase


class OperatorSettings(SettingsBase):
  """Top-level settings loaded from the canonical `config.toml` file."""

  oauth: Fac[OAuthSettings]
  database: Fac[DatabaseSettings]
  agents: Fac[AgentsSettings]
  providers: Fac[ProvidersSettings]
  models: Fac[ModelsSettings]

  @model_validator(mode="after")
  def _validate_settings(self) -> Self:
    self._validate_models()
    self._validate_archetypes()
    return self

  def _validate_models(self) -> None:
    # validate model providers
    for model in self.models.entries.values():
      if model.provider_key not in self.providers.entries:
        msg = (
          f"Model `{model.key}` sets a provider_key `{model.provider_key}` "
          "that does not exist!"
        )
        raise ValueError(msg)

  def _validate_archetypes(self) -> None:
    # validate agent models
    for agent in self.agents.archetypes.values():
      if not agent.use_preset_model:
        continue
      if agent.use_preset_model not in self.models.entries:
        msg = (
          f"Archetype `{agent.key}` sets a `use_preset_model` value of "
          f"`{agent.use_preset_model}`, but that key isn't present in "
          "`models.entries`!"
        )
        raise ValueError(msg)

  def get_model(
    self,
    key: str,
    *,
    raise_on_none: bool = False,
  ) -> _ModelSettings:
    """Return model based on key, or default one.

    If `raise_on_none` is set, will not return the default model and instead will
    raise an error if the key was not found.
    """
    if x := self.models.entries.get(key):
      return x
    if raise_on_none:
      msg = f"Model preset `{key}` was not found."
      raise ValueError(msg)
    return self.models.default_entry_force

  def get_archetype_model(self, archetype_key: str) -> _ModelSettings:
    """Return effective model preset for the archetype.

    This first looks into archetype-specific presets, falling back to the default
    model. If no default is found, raises an error.
    """
    archetype = self.agents.archetypes.get(archetype_key)
    if not archetype:
      msg = f"Couldn't find archetype `{archetype_key}`"
      raise ValueError(msg)
    if x := archetype.use_preset_model:
      # this should never fail, due to `_validate_archetypes`
      return self.get_model(x, raise_on_none=True)
    return self.models.default_entry_force

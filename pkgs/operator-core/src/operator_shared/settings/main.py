"""Shared Operator settings models and loaders."""

from operator_shared.settings.database import DatabaseSettings
from operator_shared.settings.oauth import OAuthSettings
from operator_shared.settings.types import Fac, SettingsBase


class OperatorSettings(SettingsBase):
    """Top-level settings loaded from the canonical `config.toml` file."""

    oauth: Fac[OAuthSettings]
    database: Fac[DatabaseSettings]

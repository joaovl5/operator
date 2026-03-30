from typing import TYPE_CHECKING

import pytest
from pydantic import ValidationError

from operator_shared.settings.errors import OperatorSettingsLoadError
from operator_shared.settings.main import (
    DEFAULT_CALLBACK_PORT,
    CallbackSettings,
    OAuthSettings,
    OperatorSettings,
    load_operator_settings,
 )

if TYPE_CHECKING:
    from pathlib import Path

def test_callback_settings_defaults_match_local_oauth_flow() -> None:
    """Callback settings expose the local OAuth defaults."""
    callback = CallbackSettings()

    assert callback.port == DEFAULT_CALLBACK_PORT
    assert callback.path == "/auth/callback"
    assert callback.redirect_uri() == "http://localhost:1455/auth/callback"


def test_oauth_settings_defaults_include_callback_defaults() -> None:
    """OAuth defaults embed the callback defaults."""
    oauth = OAuthSettings()

    assert oauth.callback == CallbackSettings()


def test_load_operator_settings_returns_defaults_when_file_is_missing(tmp_path: Path) -> None:
    """Missing operator.toml files fall back to default settings."""
    settings = load_operator_settings(path=tmp_path / "operator.toml")

    assert settings == OperatorSettings()


def test_load_operator_settings_reads_optional_operator_toml(tmp_path: Path) -> None:
    """A present operator.toml file is parsed and validated."""
    path = tmp_path / "operator.toml"
    _ = path.write_text(
        """
[oauth.callback]
port = 9999
path = "/oauth/callback"
""".strip(),
        encoding="utf-8",
    )

    settings = load_operator_settings(path=path)
    assert settings.oauth.callback == CallbackSettings(
        port=9999,
        path="/oauth/callback",
    )


def test_load_operator_settings_rejects_legacy_callback_keys(tmp_path: Path) -> None:
    """Legacy callback keys are rejected after the refactor cutover."""
    path = tmp_path / "operator.toml"
    _ = path.write_text(
        """
[oauth.callback]
host = "0.0.0.0"
host_uri = "legacy.localhost"
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(ValidationError, match="host"):
        _ = load_operator_settings(path=path)


def test_load_operator_settings_raises_dedicated_error_for_invalid_toml(tmp_path: Path) -> None:
    """Malformed TOML raises the dedicated loader error."""
    path = tmp_path / "operator.toml"
    _ = path.write_text("oauth = [", encoding="utf-8")

    with pytest.raises(OperatorSettingsLoadError, match=r"operator\.toml"):
        _ = load_operator_settings(path=path)


def test_load_operator_settings_preserves_pydantic_validation_errors(tmp_path: Path) -> None:
    """Schema validation failures still surface as Pydantic errors."""
    path = tmp_path / "operator.toml"
    _ = path.write_text(
        """
[oauth.callback]
port = "soon"
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(ValidationError, match="port"):
        _ = load_operator_settings(path=path)


def test_callback_settings_rejects_unsupported_port_and_path_shapes() -> None:
    """Callback settings reject unsupported port and path values."""
    with pytest.raises(ValidationError, match="port"):
        _ = CallbackSettings(port=70_000)

    with pytest.raises(ValidationError, match="path"):
        _ = CallbackSettings(path="auth/callback")

    with pytest.raises(ValidationError, match="path"):
        _ = CallbackSettings(path="/auth/callback?code=1")

    with pytest.raises(ValidationError, match="path"):
        _ = CallbackSettings(path="/auth/callback with space")

def test_callback_settings_validator_rejects_non_mapping_input() -> None:
    """Non-dict callback values now validate as errors instead of crashing."""
    with pytest.raises(ValidationError):
        _ = OperatorSettings.model_validate(
            {
                "oauth": {
                    "callback": "bad-input",
                }
            }
        )

    with pytest.raises(ValidationError):
        _ = OperatorSettings.model_validate(
            {
                "oauth": {
                    "callback": ["bad", "input"],
                }
            }
        )

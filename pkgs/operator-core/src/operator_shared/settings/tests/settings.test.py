from typing import TYPE_CHECKING

import pytest
from pydantic import ValidationError

from operator_shared.settings.errors import OperatorSettingsLoadError
from operator_shared.settings.main import (
    CallbackSettings,
    OAuthSettings,
    OperatorSettings,
    load_operator_settings,
)

if TYPE_CHECKING:
    from pathlib import Path


DEFAULT_BIND_HOST = "127.0.0.1"
EXPLICIT_BIND_HOST = "0.0.0.0"  # noqa: S104
DEFAULT_CALLBACK_PORT = 1455
DEFAULT_REFRESH_BUFFER_MS = 60_000
CUSTOM_REFRESH_BUFFER_MS = 30_000


def test_callback_settings_defaults_match_local_oauth_flow() -> None:
    """Callback settings expose the local OAuth defaults."""
    callback = CallbackSettings()

    assert callback.host == DEFAULT_BIND_HOST
    assert callback.port == DEFAULT_CALLBACK_PORT
    assert callback.path == "/auth/callback"
    assert callback.host_uri == "localhost"
    assert callback.redirect_uri() == "http://localhost:1455/auth/callback"


def test_callback_settings_bind_host_does_not_override_redirect_host() -> None:
    """Redirect generation keeps the localhost URI default."""
    callback = CallbackSettings(host=EXPLICIT_BIND_HOST)

    assert callback.redirect_uri() == "http://localhost:1455/auth/callback"


def test_callback_settings_prefers_explicit_host_uri_for_redirects() -> None:
    """An explicit URI host takes precedence over the bind host."""
    callback = CallbackSettings(host=EXPLICIT_BIND_HOST, host_uri="operator.internal")

    assert callback.redirect_uri() == "http://operator.internal:1455/auth/callback"


def test_oauth_settings_defaults_include_callback_defaults() -> None:
    """OAuth defaults embed the callback defaults."""
    oauth = OAuthSettings()

    assert oauth.refresh_buffer_ms == DEFAULT_REFRESH_BUFFER_MS
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
[oauth]
refresh_buffer_ms = 30000

[oauth.callback]
host = "0.0.0.0"
port = 9999
path = "/oauth/callback"
host_uri = "127.0.0.1.nip.io"
""".strip(),
        encoding="utf-8",
    )

    settings = load_operator_settings(path=path)

    assert settings.oauth.refresh_buffer_ms == CUSTOM_REFRESH_BUFFER_MS
    assert settings.oauth.callback == CallbackSettings(
        host=EXPLICIT_BIND_HOST,
        port=9999,
        path="/oauth/callback",
        host_uri="127.0.0.1.nip.io",
    )


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
[oauth]
refresh_buffer_ms = "soon"
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(ValidationError, match="refresh_buffer_ms"):
        _ = load_operator_settings(path=path)

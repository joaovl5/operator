import importlib
from typing import TYPE_CHECKING

from operator_core.providers.openai import OpenAIOAuthCredentials, OpenAIOAuthStore

from .support import ACCESS_TOKEN, EXPECTED_ACCOUNT_ID, REFRESH_TOKEN, make_jwt


def load_auth_main() -> ModuleType:
    """Import the auth entrypoint module lazily for this test file."""
    return importlib.import_module("operator_cli.auth.main")


if TYPE_CHECKING:
    from types import ModuleType


def test_run_openai_logout_and_status_use_core_store_boundary(tmp_path) -> None:
    """Logout and status stay thin wrappers over the core store model."""
    auth_main = load_auth_main()
    store = OpenAIOAuthStore(path=tmp_path / "openai.json")
    output_lines: list[str] = []
    _ = store.save(
        OpenAIOAuthCredentials(
            access_token=ACCESS_TOKEN,
            refresh_token=REFRESH_TOKEN,
            id_token=make_jwt({"chatgpt_account_id": EXPECTED_ACCOUNT_ID}),
            expires_at_ms=123_456,
            account_id=EXPECTED_ACCOUNT_ID,
            scope="openid profile email offline_access",
            token_type="Bearer",  # noqa: S106
        )
    )

    status_result = auth_main.run_openai_status(store=store, output=output_lines.append)
    logout_result = auth_main.run_openai_logout(store=store, output=output_lines.append)

    assert status_result == 0
    assert logout_result == 0
    assert store.load() is None
    assert EXPECTED_ACCOUNT_ID in "\n".join(output_lines)
    assert ACCESS_TOKEN not in "\n".join(output_lines)


def test_run_openai_status_reports_missing_and_present_credentials_without_secrets(
    tmp_path,
) -> None:
    """Status output reports login state and metadata while hiding tokens."""
    auth_main = load_auth_main()
    missing_store = OpenAIOAuthStore(path=tmp_path / "missing.json")
    missing_output: list[str] = []

    missing_result = auth_main.run_openai_status(store=missing_store, output=missing_output.append)

    present_store = OpenAIOAuthStore(path=tmp_path / "present.json")
    _ = present_store.save(
        OpenAIOAuthCredentials(
            access_token=ACCESS_TOKEN,
            refresh_token=REFRESH_TOKEN,
            id_token=make_jwt({"chatgpt_account_id": EXPECTED_ACCOUNT_ID}),
            expires_at_ms=123_456,
            account_id=EXPECTED_ACCOUNT_ID,
            scope="openid profile email offline_access",
            token_type="Bearer",  # noqa: S106
        )
    )
    present_output: list[str] = []

    present_result = auth_main.run_openai_status(store=present_store, output=present_output.append)
    rendered_present_output = "\n".join(present_output)

    assert missing_result == 0
    assert "not logged in" in "\n".join(missing_output).lower()
    assert present_result == 0
    assert EXPECTED_ACCOUNT_ID in rendered_present_output
    assert "expires" in rendered_present_output.lower()
    assert ACCESS_TOKEN not in rendered_present_output
    assert REFRESH_TOKEN not in rendered_present_output


def test_run_openai_logout_clears_missing_store_without_error(tmp_path) -> None:
    """Logout returns success even when no stored login is present."""
    auth_main = load_auth_main()
    output_lines: list[str] = []

    result = auth_main.run_openai_logout(
        store=OpenAIOAuthStore(path=tmp_path / "missing.json"),
        output=output_lines.append,
    )

    assert result == 0
    assert "not found" in "\n".join(output_lines).lower()

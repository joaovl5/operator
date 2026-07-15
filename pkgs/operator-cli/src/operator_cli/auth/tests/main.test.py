from typing import TYPE_CHECKING

from operator_cli.auth.main import (
  run_openai_logout,
  run_openai_status,
)
from operator_core_olden.providers.openai import (
  OpenAIOAuthCredentials,
  OpenAIOAuthStore,
)

from .support import (
  ACCESS_TOKEN,
  EXPECTED_ACCOUNT_ID,
  REFRESH_TOKEN,
  make_jwt,
)

if TYPE_CHECKING:
  from pathlib import Path


def test_run_openai_logout_and_status_use_core_store_boundary(
  tmp_path: Path,
) -> None:
  """Logout and status stay thin wrappers over the core store model."""
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

  status_result = run_openai_status(
    store=store, output=output_lines.append
  )
  logout_result = run_openai_logout(
    store=store, output=output_lines.append
  )

  assert status_result == 0
  assert logout_result == 0
  assert store.load() is None
  assert EXPECTED_ACCOUNT_ID in "\n".join(output_lines)
  assert ACCESS_TOKEN not in "\n".join(output_lines)


def test_run_openai_status_reports_missing_and_present_credentials_without_secrets(
  tmp_path: Path,
) -> None:
  """Status output reports login state and metadata while hiding tokens."""
  missing_store = OpenAIOAuthStore(path=tmp_path / "missing.json")
  missing_output: list[str] = []

  missing_result = run_openai_status(
    store=missing_store, output=missing_output.append
  )

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

  present_result = run_openai_status(
    store=present_store, output=present_output.append
  )
  rendered_present_output = "\n".join(present_output)

  assert missing_result == 0
  assert "not logged in" in "\n".join(missing_output).lower()
  assert present_result == 0
  assert EXPECTED_ACCOUNT_ID in rendered_present_output
  assert "expires" in rendered_present_output.lower()
  assert ACCESS_TOKEN not in rendered_present_output
  assert REFRESH_TOKEN not in rendered_present_output


def test_run_openai_logout_clears_missing_store_without_error(
  tmp_path: Path,
) -> None:
  """Logout returns success even when no stored login is present."""
  output_lines: list[str] = []

  result = run_openai_logout(
    store=OpenAIOAuthStore(path=tmp_path / "missing.json"),
    output=output_lines.append,
  )

  assert result == 0
  assert "not found" in "\n".join(output_lines).lower()


def test_run_openai_status_and_logout_handle_corrupt_store(
  tmp_path: Path,
) -> None:
  """Status reports corrupt auth files and logout removes them cleanly."""
  path = tmp_path / "corrupt.json"
  _ = path.write_text("{", encoding="utf-8")
  store = OpenAIOAuthStore(path=path)
  status_output: list[str] = []
  logout_output: list[str] = []

  status_result = run_openai_status(
    store=store, output=status_output.append
  )
  logout_result = run_openai_logout(
    store=store, output=logout_output.append
  )

  assert status_result == 1
  assert (
    "could not read stored login" in "\n".join(status_output).lower()
  )
  assert logout_result == 0
  assert path.exists() is False
  assert "unreadable" in "\n".join(logout_output).lower()

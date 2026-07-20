import pytest

import operator_cli.main
from operator_cli.main import build_parser, main


def test_build_parser_help_lists_openai_auth_commands() -> None:
  """Parser help exposes the nested OpenAI auth commands."""
  parser = build_parser()

  help_text = parser.format_help()

  assert "auth" in help_text
  assert "openai" in help_text
  assert "login" in help_text
  assert "logout" in help_text
  assert "status" in help_text


def test_main_dispatches_status_to_openai_auth_module(
  monkeypatch: pytest.MonkeyPatch,
) -> None:
  """CLI dispatch stays a thin wrapper around the auth module."""
  expected = 23

  def fake_status() -> int:
    return expected

  monkeypatch.setattr(
    operator_cli.main, "run_openai_status", fake_status
  )

  result = main(["auth", "openai", "status"])

  assert result == expected


@pytest.mark.parametrize(
  ("argv", "attribute", "expected"),
  [
    pytest.param(
      ["auth", "openai", "login"], "run_openai_login", 11, id="login"
    ),
    pytest.param(
      ["auth", "openai", "logout"],
      "run_openai_logout",
      12,
      id="logout",
    ),
    pytest.param(
      ["auth", "openai", "status"],
      "run_openai_status",
      13,
      id="status",
    ),
  ],
)
def test_main_dispatches_each_openai_auth_command(
  monkeypatch: pytest.MonkeyPatch,
  argv: list[str],
  attribute: str,
  expected: int,
) -> None:
  """Each auth command dispatches to its corresponding CLI helper."""

  def handler() -> int:
    return expected

  monkeypatch.setattr(operator_cli.main, attribute, handler)

  assert main(argv) == expected


@pytest.mark.parametrize("argv", [["auth"], ["auth", "openai"]])
def test_build_parser_rejects_incomplete_auth_command_shapes(
  argv: list[str],
) -> None:
  """Incomplete auth command paths fail with argparse usage errors."""
  parser = build_parser()

  with pytest.raises(SystemExit, match="2"):
    _ = parser.parse_args(argv)

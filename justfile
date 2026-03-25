alias c := check
check:
  nix fmt --quiet --log-format raw
  uv run ruff format --quiet
  uv run ruff check . --quiet
  uv run basedpyright
  uv run pytest --quiet --verbosity=-1
  mdbook test docs
  prek run --all-files --fail-fast --quiet
  nix flake check --quiet --log-format raw

docs:
  mdbook build docs

alias f := format
format:
  nix fmt --quiet --log-format raw
  uv run ruff format --quiet

commit:
  cz commit

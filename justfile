alias c := check
check:
  uv run ruff check . --quiet --no-cache
  uv run basedpyright
  PYTHONDONTWRITEBYTECODE=1 uv run python -B -m pytest --quiet --verbosity=-1 -p no:cacheprovider
  mdbook test docs

docs:
  mdbook build docs

alias f := format
format:
  nix fmt --quiet --log-format raw
  uv run ruff format --quiet

commit:
  cz commit

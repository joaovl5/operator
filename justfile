alias c := check
check:
  just format
  uv run ruff check . --quiet --no-cache
  uv run basedpyright
  PYTHONDONTWRITEBYTECODE=1 uv run python -B -m pytest --quiet --verbosity=-1 -p no:cacheprovider

docs:
  echo "TODO"

alias f := format
format:
  uv run ruff format --quiet

alias a := alchemy
alchemy *STUFF:
  uv run alchemy --config alchemy.config {{ STUFF }}

mk-migrate msg:
  @just alchemy make-migrations --autogenerate -m "{{ quote(msg) }}"

db-up:
  @just alchemy upgrade --no-prompt

db-rm:
  @just alchemy drop-all

# Agent Instructions for Operator Workspace

## Environment And Workspace

- This repo is a `uv` workspace with Python packages under `pkgs/*` and `src` module roots.
- Python 3.14 is the expected in this workspace. Do not write compatibility code for older Python versions.
- Use the Nix flake dev environment. `direnv` support is expected; otherwise use `nix develop`.
- Run Python tooling with `uv run`.

## Verification Workflow

Successful verification is obligatory for any task to be deemed
complete.

- Re-run checks before claiming work is done.
- Always use `just check` for running all verification flows unless
  requested otherwise by user in an exceptional case.
- Treat failing checks, type errors, and actionable warnings as work
  to fix, not output to ignore.
- Never use `noqa` or `pyrightIgnore` statements unless there is no
  better option. If there is a 1% chance of a better and safer
  solution, choose it.

## Python And Typing

- Always use strongly-typed and modern Python features. Remember we're
  expecting only to use Python 3.14 as a baseline.
  - Never add `from __future__ import annotations`.
  - Pattern matching with 'match' when it makes variant handling
    clearer than plain `if` clauses.
- Keep strict typing intact.
  - Never use `cast(...)` at all.
  - Avoid using `Any` unless there is no cleaner option.
- Public functions/methods should:
  - be keyword-only (with `*, foo: int, bar: str` or `self, *, foo: int, bar: str` for class methods) if they have more than one argument (besides self)
  - have docstrings with the following rules:
    - they must be concise by default (one-liners)
    - only ellaborate further for content that couldn't be discerned
      solely from the function signature at a glance (arguments that
      have non-trivial behavior or concepts that require further
      documentation are good examples)
    - treat docstrings are first-class citizens, this is the main
      documentation/reference source for non-trivial concepts.

### Data Modeling

- Use pydantic `BaseModel` for serialized, config, request, and response payloads.
- Use `@define` from `attrs` instead of dataclasses or ad-hoc state-holder classes.
- Prefer dedicated `<Thing>Error` hierarchies, usually in module-local `errors.py` files.
- _For complex variants, prefer algebraic data type style modeling over enums_:
  - model each variant as its own type with only the fields that variant needs
  - define a closed union or validating wrapper for the allowed variants
  - branch on the concrete variant with `match`/`case`
  - avoid a single enum plus many optional fields when variants carry different payloads or behavior
- Simple enums are still fine for _closed scalar choices with no payload_.
- Never use `TypedDict` or dataclasses unless there is absolutely zero
  other alternatives.

## Modules

- Module-related error handling should be dealt with subclassing an
  'Error' or 'Exception' class, that way there's a structured
  hierarchy for usage i `try ... except` blocks.
  - Avoid reliance on error messages, use subclasses for
    specificity, each module having a base error class for other more
    specific error cases to inherit.
  - Extra info (debugging or user-facing messages) can be injected as
    payload for error classes.
  - Naming suffix should be 'Error' and not 'Exception'
  - When error has payload, overload `__repr__` for a user/dev-facing
    string representation of the error.

### Layout And Boundaries

- When a module grows beyond one clear responsibility, split it into a package with this shape when it improves clarity:
  - `__init__.py` for public exports
  - `errors.py` for exception types
  - `types.py` for models and typed payloads
  - `main.py` for core logic
  - `utils.py` for focused helpers
  - `tests/` next to the module
- Put shared cross-domain code in `operator_shared`.
- Prefer `httpx` over `urllib`.
- Do not implement unfinished or user-WIP areas speculatively. Keep placeholders lint-safe and type-safe instead.

## Package Ownership

- `operator-cli` is frontend-only. It should orchestrate UX and delegate backend concerns.
- `operator-core` owns settings, OAuth protocol behavior, credential storage, refresh logic, and provider/client construction.

## Testing Rules

- Put tests next to the code they cover under `pkgs/*/src/**/tests/*.test.py`.
- Overlapping cases should get merged for easier reading of tests,
  through parametrization.
- Favor public-behavior (black/grey-box) tests over private-logic
  (white-box) tests.
  - Avoid assertions on private logic, internal delegation unless they
    protect a real external guarantee that could not be gotten simply
    through public-faced assertions.
  - Keep tests that protect externally-seen garantees, especially
    around state, persistence, protocol behavior, concurrency or other
    user-observable outcomes when relevant.

## Packaging And Build Rules

- In-package tests must stay excluded from source and wheel distributions.
- Keep package metadata and verification config aligned with the real workspace layout.
- If a check is not describing the real repo state, fix the tooling/config first so verification stays truthful.

## Change Strategy

- Prefer staged, verification-first refactors over broad rewrites.
- Keep changes simple, with clear module boundaries and minimal surface area.
- Preserve established ownership and behavior in touched areas unless the user explicitly asks for a change.

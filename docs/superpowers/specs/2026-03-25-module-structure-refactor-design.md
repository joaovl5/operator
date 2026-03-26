# Module Structure Refactor Design

## Goal

Restructure the current `operator_core` and `operator_cli` module layout so that runtime logic, provider implementations, shared forms, permissions, toolsets, and CLI auth flows live in focused packages with clear ownership and minimal cross-domain coupling.

## Why This Refactor

The current layout has a few pressure points that now work against the repository rules in `AGENTS.md`:

- `pkgs/operator-core/src/operator_core/agent.py` combines provider configuration, provider implementations, agent runtime behavior, permission schemas, and toolset/form models in one file.
- OpenAI provider logic is split across multiple top-level modules (`agent.py`, `openai_client`, `openai_oauth`, `openai_store`) instead of one provider-oriented package tree.
- `pkgs/operator-cli/src/operator_cli/openai_auth/main.py` mixes public auth entrypoints, callback listener behavior, OpenAI-specific flow logic, and helper wiring in one module.
- Shared form primitives currently live inside `operator_core` even though they are cross-domain concepts.

The refactor should make the tree reflect the actual domain boundaries so future work lands in the right module the first time.

## Decisions

- Follow the package-oriented layout encouraged by `AGENTS.md` rather than keeping large flat modules.
- Use `types.py` and `main.py` instead of `config.py` and `runtime.py`.
- Move shared form primitives into `operator_shared`.
- Recurse permissions types under `permissions/types/{communication,permission,temporal}.py`.
- Recurse provider implementations under `providers/openai/` and a reusable store utility package under `providers/utils/store/`.
- Do not keep compatibility re-exports at the old import paths. This is a deliberate import rewrite.
- Do not add migration-only tests. Tests must continue to protect durable behavior after the refactor is complete.

## Target Package Layout

The intended end state is:

```text
pkgs/operator-core/src/operator_core/
  agent/
    __init__.py
    main.py
    types.py
    errors.py
    tests/
  permissions/
    __init__.py
    types/
      __init__.py
      communication.py
      permission.py
      temporal.py
    tests/
  providers/
    __init__.py
    main.py
    types.py
    errors.py
    openai/
      __init__.py
      client.py
      oauth.py
      types.py
      errors.py
      tests/
    utils/
      __init__.py
      store/
        __init__.py
        main.py
        types.py
        errors.py
        utils.py
        tests/
  toolsets/
    __init__.py
    types.py
    errors.py
    tests/

pkgs/operator-core/src/operator_shared/
  forms.py

pkgs/operator-cli/src/operator_cli/
  auth/
    __init__.py
    main.py
    types.py
    openai_oauth.py
    tests/
```

## Ownership Boundaries

### `operator_shared.forms`

`operator_shared.forms` owns only cross-domain form primitives:

- `BaseForm`
- `ObjectMetadata`

This module depends on `pydantic` only. It must not depend on `operator_core` or `operator_cli`.

### `operator_core.permissions`

`operator_core.permissions` owns schema-only permission and communication models.

- `types/communication.py` owns communication-state models and aliases.
- `types/permission.py` owns filesystem/subagent permission models and permission items.
- `types/temporal.py` owns temporal scope models and aliases.

This package should remain independent from providers, agent runtime, and CLI auth.

### `operator_core.toolsets`

`operator_core.toolsets` owns toolset schemas.

- `Toolset`
- `ToolsetAction`

It may depend on `operator_shared.forms` and permission models, but it must not contain provider logic or agent runtime behavior.

As part of the import rewrite, `Toolset` and `ToolsetAction` must be removed from any agent-owned or provider-owned modules.

### `operator_core.providers`

`operator_core.providers` owns provider abstractions and shared provider-facing contracts.

- `providers/main.py` contains only shared provider interfaces and base behavior that is provider-agnostic.
- `providers/types.py` contains provider-level typed payloads and configuration contracts.
- `providers/errors.py` contains provider-level base errors.

`providers/main.py` must not become a new mixed-responsibility hub. It should not contain OpenAI-specific logic, OAuth-specific rules, store mechanics, permission models, toolset models, or agent runtime code.

This is the package that `operator_core.agent` consumes.

### `operator_core.providers.openai`

`operator_core.providers.openai` owns all OpenAI-specific provider logic that is currently scattered across `operator_core.agent`, `operator_core.openai_client`, and `operator_core.openai_oauth`.

- `client.py` contains plain OpenAI client/provider construction.
- `oauth.py` contains OAuth-backed provider behavior and OAuth-specific model validation.
- `types.py` contains `OpenAIModelSettings` and OpenAI-specific typed payloads.
- `errors.py` contains OpenAI-specific provider errors.

The new package becomes the sole OpenAI provider boundary in `operator_core`.

### `operator_core.providers.utils.store`

`operator_core.providers.utils.store` owns reusable credential-store mechanics.

- lock coordination
- atomic file updates
- typed store metadata/state
- reusable storage errors

The storage mechanism should be provider-agnostic. OpenAI-specific credential payloads should remain in the OpenAI provider package and be adapted at the boundary. No provider-specific schemas or naming should leak into this package.

### `operator_core.agent`

`operator_core.agent` becomes runtime-oriented only.

- `main.py` owns `OperatorAgent` and agent runtime orchestration.
- `types.py` exists as part of the required package shape and owns agent-local typed payloads, aliases, or other runtime-facing type definitions only.
- `errors.py` exists as part of the required package shape and owns agent-local runtime errors only.

Because this package shape was explicitly requested, `types.py` and `errors.py` are part of the target structure even if they stay small. They must remain lint-safe and limited to true agent concerns rather than becoming catch-all spillover modules.

`operator_core.agent` should depend on providers and any other shared packages only where its runtime surface genuinely needs them. Providers, permissions, toolsets, and shared forms must not depend back on agent runtime.

### `operator_cli.auth`

`operator_cli.auth` becomes the CLI auth boundary.

- `main.py` keeps the public auth orchestration entrypoints.
- `types.py` owns callback/listener/auth flow payloads.
- `openai_oauth.py` owns OpenAI-specific CLI auth flow internals that are currently mixed into the old `openai_auth/main.py`.

This package consumes `operator_core` services but should not own backend OAuth or credential logic itself.

## Migration Rules

This refactor is a direct tree rewrite, not a compatibility migration.

- Existing imports must be updated to the new package paths in the same refactor.
- Old module paths such as `operator_core.agent`, `operator_core.openai_client`, `operator_core.openai_oauth`, and `operator_cli.openai_auth` should not remain as compatibility facades.
- Tests move with the modules they cover so the final repository layout matches the new ownership model immediately.

## Execution Strategy

The refactor should still be implemented in structural slices so each step leaves the repository coherent:

1. Establish the new low-level destinations:
   - `operator_shared/forms.py`
   - `operator_core/permissions/...`
   - `operator_core/toolsets/...`
2. Introduce provider package boundaries:
   - `operator_core/providers/...`
   - `operator_core/providers/openai/...`
   - `operator_core/providers/utils/store/...`
3. Reduce `operator_core/agent` to runtime-only concerns.
4. Move CLI auth into `operator_cli/auth/...`.
5. Rewrite all imports and relocate tests with their owning packages.
6. Remove the superseded old modules once no imports remain.

Each slice should be small enough that it can be verified independently and reviewed without reconstructing the whole tree mentally.

## Testing Strategy

Testing must protect durable behavior, not the fact that a migration happened.

- Move existing tests with the code they actually cover.
- Add new tests only when the refactor creates a real long-term public contract or exposes behavior that previously had no lasting coverage.
- Do not add ad-hoc migration-only tests that would become pointless once the refactor lands.
- Use focused test runs during each slice, then run `just check` before claiming the slice is complete.

## Non-Goals

- No compatibility import shims.
- No speculative new features mixed into the refactor.
- No broad behavioral changes to OAuth, credential storage, or CLI UX unless required by the structural move.
- No placeholder business logic just to satisfy a target file tree.

## Success Criteria

The refactor is successful when:

- `agent.py` no longer exists as a monolithic mixed-responsibility module.
- OpenAI provider code lives under `operator_core.providers.openai`.
- shared form primitives live in `operator_shared.forms`.
- permissions, toolsets, agent runtime, provider implementations, and CLI auth have separate bounded homes.
- all imports point at the new package structure directly.
- existing durable tests still pass after being relocated.
- `just check` passes for the final tree.

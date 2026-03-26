# Recursive Module Structure Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the current flat `operator_core` and `operator_cli` OpenAI/agent/auth modules with the approved recursive package structure while preserving durable behavior and passing repository-wide verification.

**Architecture:** Move shared forms, permissions, toolsets, providers, OpenAI provider code, reusable credential-store logic, agent runtime, and CLI auth into focused packages with one-way dependencies. Perform the refactor in structural slices so each slice moves durable tests with the code it owns, rewrites imports to the new paths, and leaves the tree coherent before the next slice.

**Tech Stack:** Python 3.14, attrs, pydantic, pydantic-ai, httpx, pytest, basedpyright, Ruff, `uv`, `just`

---

## File Structure

### New core package layout

- Create: `pkgs/operator-core/src/operator_shared/forms.py` - shared `BaseForm` and `ObjectMetadata`
- Create: `pkgs/operator-core/src/operator_shared/tests/forms.test.py` - durable tests for shared form behavior
- Create: `pkgs/operator-core/src/operator_core/permissions/__init__.py` - permission package exports
- Create: `pkgs/operator-core/src/operator_core/permissions/types/__init__.py` - nested permission type exports
- Create: `pkgs/operator-core/src/operator_core/permissions/types/communication.py` - communication models and aliases
- Create: `pkgs/operator-core/src/operator_core/permissions/types/permission.py` - filesystem/subagent permission models and permission items
- Create: `pkgs/operator-core/src/operator_core/permissions/types/temporal.py` - temporal scope models and aliases
- Create: `pkgs/operator-core/src/operator_core/permissions/tests/types.test.py` - durable permission/temporal tests
- Create: `pkgs/operator-core/src/operator_core/toolsets/__init__.py` - toolset exports
- Create: `pkgs/operator-core/src/operator_core/toolsets/types.py` - `Toolset` and `ToolsetAction`
- Create: `pkgs/operator-core/src/operator_core/toolsets/errors.py` - toolset-local base errors if needed for shape; keep minimal and lint-safe
- Create: `pkgs/operator-core/src/operator_core/toolsets/tests/types.test.py` - durable toolset schema tests
- Create: `pkgs/operator-core/src/operator_core/providers/__init__.py` - provider package exports
- Create: `pkgs/operator-core/src/operator_core/providers/main.py` - provider-agnostic interfaces and base behavior only
- Create: `pkgs/operator-core/src/operator_core/providers/types.py` - provider-level config contracts
- Create: `pkgs/operator-core/src/operator_core/providers/errors.py` - provider-level base errors
- Create: `pkgs/operator-core/src/operator_core/providers/openai/__init__.py` - OpenAI provider exports
- Create: `pkgs/operator-core/src/operator_core/providers/openai/client.py` - plain OpenAI client/provider assembly
- Create: `pkgs/operator-core/src/operator_core/providers/openai/oauth.py` - OAuth-backed OpenAI provider/runtime helpers
- Create: `pkgs/operator-core/src/operator_core/providers/openai/types.py` - OpenAI model config/settings and OAuth payloads
- Create: `pkgs/operator-core/src/operator_core/providers/openai/errors.py` - OpenAI provider errors
- Create: `pkgs/operator-core/src/operator_core/providers/openai/tests/types.test.py` - OpenAI config/settings tests
- Create: `pkgs/operator-core/src/operator_core/providers/openai/tests/client.test.py` - OpenAI client/provider tests
- Create: `pkgs/operator-core/src/operator_core/providers/openai/tests/oauth.test.py` - OpenAI OAuth protocol/provider tests
- Create: `pkgs/operator-core/src/operator_core/providers/utils/__init__.py` - provider utility exports
- Create: `pkgs/operator-core/src/operator_core/providers/utils/store/__init__.py` - reusable store exports
- Create: `pkgs/operator-core/src/operator_core/providers/utils/store/main.py` - provider-agnostic JSON credential store and transaction flow
- Create: `pkgs/operator-core/src/operator_core/providers/utils/store/types.py` - reusable store lock snapshot / typing helpers
- Create: `pkgs/operator-core/src/operator_core/providers/utils/store/errors.py` - reusable store errors
- Create: `pkgs/operator-core/src/operator_core/providers/utils/store/utils.py` - reusable store path/lock helpers
- Create: `pkgs/operator-core/src/operator_core/providers/utils/store/tests/main.test.py` - durable reusable-store tests
- Create: `pkgs/operator-core/src/operator_core/agent/__init__.py` - agent package exports
- Create: `pkgs/operator-core/src/operator_core/agent/main.py` - `OperatorAgent`
- Create: `pkgs/operator-core/src/operator_core/agent/types.py` - `OperatorSession` and other runtime-local aliases that remain
- Create: `pkgs/operator-core/src/operator_core/agent/errors.py` - agent-local runtime errors only
- Create: `pkgs/operator-core/src/operator_core/agent/tests/main.test.py` - agent runtime tests

### New CLI package layout

- Create: `pkgs/operator-cli/src/operator_cli/auth/__init__.py` - CLI auth exports
- Create: `pkgs/operator-cli/src/operator_cli/auth/main.py` - public CLI auth entrypoints
- Create: `pkgs/operator-cli/src/operator_cli/auth/types.py` - auth payloads, protocols, and auth-local error classes
- Create: `pkgs/operator-cli/src/operator_cli/auth/openai_oauth.py` - OpenAI-specific CLI auth flow internals
- Create: `pkgs/operator-cli/src/operator_cli/auth/tests/main.test.py` - CLI auth entrypoint tests
- Create: `pkgs/operator-cli/src/operator_cli/auth/tests/openai_oauth.test.py` - OpenAI CLI auth flow tests

### Existing files to split, rewrite, or remove

- Modify then delete: `pkgs/operator-core/src/operator_core/agent.py`
- Modify then delete: `pkgs/operator-core/src/operator_core/openai_client/__init__.py`
- Modify then delete: `pkgs/operator-core/src/operator_core/openai_client/main.py`
- Modify then delete: `pkgs/operator-core/src/operator_core/openai_client/types.py`
- Modify then delete: `pkgs/operator-core/src/operator_core/openai_client/errors.py`
- Modify then delete: `pkgs/operator-core/src/operator_core/openai_client/utils.py`
- Modify then delete: `pkgs/operator-core/src/operator_core/openai_oauth/__init__.py`
- Modify then delete: `pkgs/operator-core/src/operator_core/openai_oauth/main.py`
- Modify then delete: `pkgs/operator-core/src/operator_core/openai_oauth/types.py`
- Modify then delete: `pkgs/operator-core/src/operator_core/openai_oauth/errors.py`
- Modify then delete: `pkgs/operator-core/src/operator_core/openai_oauth/utils.py`
- Modify then delete: `pkgs/operator-core/src/operator_core/openai_store/__init__.py`
- Modify then delete: `pkgs/operator-core/src/operator_core/openai_store/main.py`
- Modify then delete: `pkgs/operator-core/src/operator_core/openai_store/types.py`
- Modify then delete: `pkgs/operator-core/src/operator_core/openai_store/errors.py`
- Modify then delete: `pkgs/operator-core/src/operator_core/openai_store/utils.py`
- Modify then delete: `pkgs/operator-cli/src/operator_cli/openai_auth/__init__.py`
- Modify then delete: `pkgs/operator-cli/src/operator_cli/openai_auth/main.py`
- Modify then delete: `pkgs/operator-cli/src/operator_cli/openai_auth/types.py`
- Modify then delete: `pkgs/operator-cli/src/operator_cli/openai_auth/errors.py`
- Modify then delete: `pkgs/operator-cli/src/operator_cli/openai_auth/utils.py`
- Modify: `pkgs/operator-core/src/operator_core/tests/agent.test.py`
- Modify: `pkgs/operator-core/src/operator_core/openai_client/tests/openai_client.test.py`
- Modify: `pkgs/operator-core/src/operator_core/openai_oauth/tests/openai_oauth.test.py`
- Modify: `pkgs/operator-core/src/operator_core/openai_store/tests/openai_store.test.py`
- Modify: `pkgs/operator-cli/src/operator_cli/openai_auth/tests/openai_auth.test.py`
- Modify: `pkgs/operator-cli/src/operator_cli/tests/main.test.py`
- Modify: `pkgs/operator-cli/src/operator_cli/main.py`
- Modify: `pkgs/operator-core/src/operator_core/session.py`

### Key implementation decisions to preserve

- `ModelProvider` becomes generic over a provider-owned config type so provider-agnostic contracts do not depend on OpenAI settings.
- `providers/openai/types.py` owns `OpenAIModelSettings`, `OpenAIModelConfig`, OAuth request/response payloads, and credential models.
- `providers/utils/store/main.py` becomes provider-agnostic by accepting a Pydantic model type for validation/serialization instead of hard-coding `OpenAIOAuthCredentials`.
- `providers/utils/store/utils.py` owns generic path-keyed lock coordination, lock contents, stale-lock handling, and atomic JSON write helpers, including the current refresh-lock behavior.
- `providers/openai/oauth.py` owns the OpenAI-only credential path builder, OAuth endpoints/constants, PKCE/state/account-id helpers, token exchange/refresh helpers, `OpenAIOAuthManager`, and the OpenAI adapter over the reusable store.
- `providers/openai/client.py` owns plain OpenAI client creation, `CHATGPT_CODEX_BASE_URL`, `OPERATOR_ORIGINATOR`, `build_chatgpt_oauth_client`, and non-OAuth provider assembly.
- `operator_cli/auth/types.py` owns the old CLI auth error classes because the approved target tree does not include `auth/errors.py`.
- No compatibility import shims remain once the refactor is complete.

### Task 1: Extract shared forms, permissions, and toolsets

**Files:**

- Create: `pkgs/operator-core/src/operator_shared/forms.py`
- Create: `pkgs/operator-core/src/operator_shared/tests/forms.test.py`
- Create: `pkgs/operator-core/src/operator_core/permissions/__init__.py`
- Create: `pkgs/operator-core/src/operator_core/permissions/types/__init__.py`
- Create: `pkgs/operator-core/src/operator_core/permissions/types/communication.py`
- Create: `pkgs/operator-core/src/operator_core/permissions/types/permission.py`
- Create: `pkgs/operator-core/src/operator_core/permissions/types/temporal.py`
- Create: `pkgs/operator-core/src/operator_core/permissions/tests/types.test.py`
- Create: `pkgs/operator-core/src/operator_core/toolsets/__init__.py`
- Create: `pkgs/operator-core/src/operator_core/toolsets/types.py`
- Create: `pkgs/operator-core/src/operator_core/toolsets/errors.py`
- Create: `pkgs/operator-core/src/operator_core/toolsets/tests/types.test.py`
- Modify: `pkgs/operator-core/src/operator_core/tests/agent.test.py`

- [ ] **Step 1: Write the failing tests**

Move the durable non-provider coverage out of `pkgs/operator-core/src/operator_core/tests/agent.test.py` into the future-owned test files so those tests import the new packages before the implementation exists.

```python
from operator_shared.forms import BaseForm
from operator_core.permissions import Permission, PermissionItem, TemporalScope
from operator_core.toolsets import Toolset, ToolsetAction


def test_base_form_to_markdown_stays_explicitly_unimplemented() -> None:
    class SampleForm(BaseForm):
        value: str

    with pytest.raises(NotImplementedError, match="to_markdown"):
        _ = SampleForm(value="hello").to_markdown()


def test_temporal_scope_session_is_accepted_as_a_safe_placeholder() -> None:
    permission_item = PermissionItem(
        permission=Permission.Subagent(),
        temporal_scope=TemporalScope.Session(),
    )
    assert isinstance(permission_item.temporal_scope, TemporalScope.Session)
```

- [ ] **Step 2: Run the focused tests to verify they fail**

Run: `uv run pytest pkgs/operator-core/src/operator_shared/tests/forms.test.py pkgs/operator-core/src/operator_core/permissions/tests/types.test.py pkgs/operator-core/src/operator_core/toolsets/tests/types.test.py -q`
Expected: FAIL with import errors because `operator_shared.forms`, `operator_core.permissions`, and `operator_core.toolsets` do not exist yet.

- [ ] **Step 3: Write the minimal implementation**

Create the new packages and move the non-provider schema code out of `pkgs/operator-core/src/operator_core/agent.py`.

```python
# pkgs/operator-core/src/operator_shared/forms.py
class ObjectMetadata(BaseModel):
    name: str = Field(description="Short name, used as its identifier.")
    description: str = Field(description="Brief summary telling when to use it.")
    detail: str = Field(description="Comprehensive handling details.")


class BaseForm(BaseModel):
    def to_json(self) -> dict[str, Any]:
        return self.model_dump(mode="json", warnings="error")

    def get_title(self) -> str:
        return self.__repr_name__()

    def to_markdown(self) -> str:
        raise NotImplementedError("BaseForm.to_markdown is not implemented yet")
```

```python
# pkgs/operator-core/src/operator_core/toolsets/types.py
class ToolsetAction[InType: BaseForm, OutType: BaseForm](BaseForm):
    metadata: ObjectMetadata
    input_model: InType
    output_model: OutType


class Toolset[InType: BaseForm, OutType: BaseForm](BaseForm):
    metadata: ObjectMetadata
    actions: list[ToolsetAction[InType, OutType]]
```

- [ ] **Step 4: Run the focused tests to verify they pass**

Run: `uv run pytest pkgs/operator-core/src/operator_shared/tests/forms.test.py pkgs/operator-core/src/operator_core/permissions/tests/types.test.py pkgs/operator-core/src/operator_core/toolsets/tests/types.test.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add pkgs/operator-core/src/operator_shared/forms.py pkgs/operator-core/src/operator_shared/tests/forms.test.py pkgs/operator-core/src/operator_core/permissions pkgs/operator-core/src/operator_core/toolsets pkgs/operator-core/src/operator_core/tests/agent.test.py
git commit -m "refactor: extract shared forms and schema packages"
```

### Task 2: Introduce provider contracts and OpenAI config types

**Files:**

- Create: `pkgs/operator-core/src/operator_core/providers/__init__.py`
- Create: `pkgs/operator-core/src/operator_core/providers/main.py`
- Create: `pkgs/operator-core/src/operator_core/providers/types.py`
- Create: `pkgs/operator-core/src/operator_core/providers/errors.py`
- Create: `pkgs/operator-core/src/operator_core/providers/openai/types.py`
- Create: `pkgs/operator-core/src/operator_core/providers/openai/tests/types.test.py`
- Modify: `pkgs/operator-core/src/operator_core/tests/agent.test.py`

- [ ] **Step 1: Write the failing tests**

Move the provider-config tests out of `pkgs/operator-core/src/operator_core/tests/agent.test.py` into `pkgs/operator-core/src/operator_core/providers/openai/tests/types.test.py` and update them to import the future provider packages.

```python
from operator_core.providers.openai.types import OpenAIModelConfig, OpenAIModelSettings


def test_openai_model_config_validates_settings_as_base_model() -> None:
    config = OpenAIModelConfig.model_validate(
        {"name": "gpt-4.1", "settings": {"openai_store": True}}
    )
    assert isinstance(config.settings, OpenAIModelSettings)
```

- [ ] **Step 2: Run the focused tests to verify they fail**

Run: `uv run pytest pkgs/operator-core/src/operator_core/providers/openai/tests/types.test.py -q`
Expected: FAIL with import errors because the new provider packages do not exist yet.

- [ ] **Step 3: Write the minimal implementation**

Create a provider-agnostic root and keep OpenAI-specific settings/coercion in the OpenAI package.

```python
# pkgs/operator-core/src/operator_core/providers/types.py
class ModelConfig(BaseModel):
    name: str
    temperature: float = 0.1


# pkgs/operator-core/src/operator_core/providers/main.py
class ModelProvider[ConfigType: BaseModel](ABC):
    @abstractmethod
    def build_model(self, *, model_config: ConfigType) -> Model:
        ...


# pkgs/operator-core/src/operator_core/providers/openai/types.py
class OpenAIModelSettings(BaseModel):
    openai_store: bool | None = None
    openai_send_reasoning_ids: bool | None = None
    openai_previous_response_id: str | None = None


class OpenAIModelConfig(ModelConfig):
    settings: OpenAIModelSettings = Field(default_factory=OpenAIModelSettings)
```

- [ ] **Step 4: Run the focused tests to verify they pass**

Run: `uv run pytest pkgs/operator-core/src/operator_core/providers/openai/tests/types.test.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add pkgs/operator-core/src/operator_core/providers pkgs/operator-core/src/operator_core/providers/openai/types.py pkgs/operator-core/src/operator_core/providers/openai/tests/types.test.py pkgs/operator-core/src/operator_core/tests/agent.test.py
git commit -m "refactor: introduce provider contracts and OpenAI config types"
```

### Task 3: Extract the reusable store and replace `openai_store` immediately

**Files:**

- Create: `pkgs/operator-core/src/operator_core/providers/utils/__init__.py`
- Create: `pkgs/operator-core/src/operator_core/providers/utils/store/__init__.py`
- Create: `pkgs/operator-core/src/operator_core/providers/utils/store/main.py`
- Create: `pkgs/operator-core/src/operator_core/providers/utils/store/types.py`
- Create: `pkgs/operator-core/src/operator_core/providers/utils/store/errors.py`
- Create: `pkgs/operator-core/src/operator_core/providers/utils/store/utils.py`
- Create: `pkgs/operator-core/src/operator_core/providers/utils/store/tests/main.test.py`
- Create: `pkgs/operator-core/src/operator_core/providers/openai/__init__.py`
- Create: `pkgs/operator-core/src/operator_core/providers/openai/oauth.py`
- Create: `pkgs/operator-core/src/operator_core/providers/openai/errors.py`
- Modify: `pkgs/operator-core/src/operator_core/openai_client/tests/openai_client.test.py`
- Modify: `pkgs/operator-core/src/operator_core/tests/agent.test.py`
- Delete: `pkgs/operator-core/src/operator_core/openai_store/tests/openai_store.test.py`
- Delete: `pkgs/operator-core/src/operator_core/openai_store/__init__.py`
- Delete: `pkgs/operator-core/src/operator_core/openai_store/main.py`
- Delete: `pkgs/operator-core/src/operator_core/openai_store/types.py`
- Delete: `pkgs/operator-core/src/operator_core/openai_store/errors.py`
- Delete: `pkgs/operator-core/src/operator_core/openai_store/utils.py`

- [ ] **Step 1: Write the failing tests**

Move the durable lock-file and JSON persistence behavior out of `pkgs/operator-core/src/operator_core/openai_store/tests/openai_store.test.py` into `pkgs/operator-core/src/operator_core/providers/utils/store/tests/main.test.py`, replacing `OpenAIOAuthCredentials` fixtures with a local Pydantic test model so the tests describe reusable store behavior rather than OpenAI behavior. Delete the legacy test file in the same slice after its durable coverage has moved. In the same red phase, rewrite any durable tests that still import `operator_core.openai_store` so they point at the future `operator_core.providers.openai` adapter or `operator_core.providers.utils.store` package.

```python
class SampleCredentials(BaseModel):
    access_token: str
    refresh_token: str


def test_store_public_apis_save_load_update_and_delete(tmp_path: Path) -> None:
    store = JsonCredentialStore[SampleCredentials](
        credential_type=SampleCredentials,
        path=tmp_path / "credentials.json",
    )
    saved = store.save(SampleCredentials(access_token="a", refresh_token="b"))
    assert saved.access_token == "a"
```

- [ ] **Step 2: Run the focused tests to verify they fail**

Run: `uv run pytest pkgs/operator-core/src/operator_core/providers/utils/store/tests/main.test.py pkgs/operator-core/src/operator_core/openai_client/tests/openai_client.test.py pkgs/operator-core/src/operator_core/tests/agent.test.py -q`
Expected: FAIL with missing store symbols at the new paths until the reusable store and OpenAI adapter exist.

- [ ] **Step 3: Write the minimal implementation**

Implement the provider-agnostic store plus the first OpenAI adapter and rewrite imports off the old `openai_store` package in the same slice.

```python
class JsonCredentialStore[CredentialType: BaseModel]:
    def __init__(self, *, credential_type: type[CredentialType], path: Path) -> None:
        self.credential_type = credential_type
        self.path = path
        self.lock_path = path.with_name(f"{path.name}.lock")


class OpenAIOAuthStore(JsonCredentialStore[OpenAIOAuthCredentials]):
    def __init__(self, *, path: Path | None = None, base_dir: Path | None = None) -> None:
        super().__init__(
            credential_type=OpenAIOAuthCredentials,
            path=default_openai_credentials_path(path=path, base_dir=base_dir),
        )
```

Put the default OpenAI credential path helper in `pkgs/operator-core/src/operator_core/providers/openai/oauth.py`, and move generic lock helpers like the refresh lock into `pkgs/operator-core/src/operator_core/providers/utils/store/utils.py`.

- [ ] **Step 4: Run the focused tests to verify they pass**

Run: `uv run pytest pkgs/operator-core/src/operator_core/providers/utils/store/tests/main.test.py pkgs/operator-core/src/operator_core/openai_client/tests/openai_client.test.py pkgs/operator-core/src/operator_core/tests/agent.test.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add pkgs/operator-core/src/operator_core/providers/utils pkgs/operator-core/src/operator_core/providers/openai pkgs/operator-core/src/operator_core/openai_client/tests/openai_client.test.py pkgs/operator-core/src/operator_core/tests/agent.test.py
git commit -m "refactor: replace OpenAI store with reusable provider store"
```

### Task 4: Move OAuth protocol helpers and models into `providers/openai`

**Files:**

- Modify: `pkgs/operator-core/src/operator_core/providers/openai/__init__.py`
- Modify: `pkgs/operator-core/src/operator_core/providers/openai/oauth.py`
- Modify: `pkgs/operator-core/src/operator_core/providers/openai/types.py`
- Modify: `pkgs/operator-core/src/operator_core/providers/openai/errors.py`
- Create: `pkgs/operator-core/src/operator_core/providers/openai/tests/oauth.test.py`
- Modify: `pkgs/operator-cli/src/operator_cli/openai_auth/tests/openai_auth.test.py`
- Delete: `pkgs/operator-core/src/operator_core/openai_oauth/tests/openai_oauth.test.py`
- Delete: `pkgs/operator-core/src/operator_core/openai_oauth/__init__.py`
- Delete: `pkgs/operator-core/src/operator_core/openai_oauth/main.py`
- Delete: `pkgs/operator-core/src/operator_core/openai_oauth/types.py`
- Delete: `pkgs/operator-core/src/operator_core/openai_oauth/errors.py`
- Delete: `pkgs/operator-core/src/operator_core/openai_oauth/utils.py`

- [ ] **Step 1: Write the failing tests**

Move the durable OAuth protocol tests out of `pkgs/operator-core/src/operator_core/openai_oauth/tests/openai_oauth.test.py` into `pkgs/operator-core/src/operator_core/providers/openai/tests/oauth.test.py`, then delete the legacy test file in the same slice. Rewrite any CLI auth tests that import `operator_core.openai_oauth` so they target the future `operator_core.providers.openai` exports.

```python
from operator_core.providers.openai import (
    AuthorizeRequest,
    OpenAIOAuthCredentials,
    OpenAIOAuthReauthRequiredError,
    OpenAIOAuthStateMismatchError,
    OpenAITokenResponse,
    build_authorize_url,
    build_pkce_verifier_and_challenge,
    exchange_authorization_code,
    generate_oauth_state,
    refresh_access_token,
    validate_oauth_state,
)
```

- [ ] **Step 2: Run the focused tests to verify they fail**

Run: `uv run pytest pkgs/operator-core/src/operator_core/providers/openai/tests/oauth.test.py pkgs/operator-cli/src/operator_cli/openai_auth/tests/openai_auth.test.py -q`
Expected: FAIL with missing exports or broken OAuth wiring at the new package path.

- [ ] **Step 3: Write the minimal implementation**

Move the OAuth constants, request/response models, protocol helpers, and public OAuth errors into `providers/openai`, then rewrite imports so no code references `operator_core.openai_oauth` anymore.

```python
# pkgs/operator-core/src/operator_core/providers/openai/oauth.py
OPENAI_OAUTH_AUTHORIZE_ENDPOINT = "https://auth.openai.com/oauth/authorize"
OPENAI_OAUTH_CLIENT_ID = "..."


def generate_oauth_state() -> str:
    return secrets.token_urlsafe(32)


def validate_oauth_state(*, received_state: str, pending_state: str) -> str:
    if received_state != pending_state:
        raise OpenAIOAuthStateMismatchError("OAuth state mismatch")
    return received_state
```

- [ ] **Step 4: Run the focused tests to verify they pass**

Run: `uv run pytest pkgs/operator-core/src/operator_core/providers/openai/tests/oauth.test.py pkgs/operator-cli/src/operator_cli/openai_auth/tests/openai_auth.test.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add pkgs/operator-core/src/operator_core/providers/openai pkgs/operator-cli/src/operator_cli/openai_auth/tests/openai_auth.test.py
git commit -m "refactor: relocate OpenAI OAuth protocol code"
```

### Task 5: Move OpenAI client and provider classes into `providers/openai`

**Files:**

- Modify: `pkgs/operator-core/src/operator_core/providers/openai/__init__.py`
- Create: `pkgs/operator-core/src/operator_core/providers/openai/client.py`
- Create: `pkgs/operator-core/src/operator_core/providers/openai/tests/client.test.py`
- Modify: `pkgs/operator-core/src/operator_core/tests/agent.test.py`
- Delete: `pkgs/operator-core/src/operator_core/openai_client/tests/openai_client.test.py`
- Delete: `pkgs/operator-core/src/operator_core/openai_client/__init__.py`
- Delete: `pkgs/operator-core/src/operator_core/openai_client/main.py`
- Delete: `pkgs/operator-core/src/operator_core/openai_client/types.py`
- Delete: `pkgs/operator-core/src/operator_core/openai_client/errors.py`
- Delete: `pkgs/operator-core/src/operator_core/openai_client/utils.py`

- [ ] **Step 1: Write the failing tests**

Move the durable OpenAI client/provider tests out of `pkgs/operator-core/src/operator_core/openai_client/tests/openai_client.test.py` into `pkgs/operator-core/src/operator_core/providers/openai/tests/client.test.py`, then delete the legacy test file in the same slice. Rewrite the remaining provider build-model tests from `pkgs/operator-core/src/operator_core/tests/agent.test.py` so they target the new package.

```python
from operator_core.providers.openai import (
    CHATGPT_CODEX_BASE_URL,
    OpenAIModelProvider,
    OpenAIOAuthManager,
    OpenAIOAuthModelProvider,
    build_chatgpt_oauth_client,
    get_openai_client,
)
```

- [ ] **Step 2: Run the focused tests to verify they fail**

Run: `uv run pytest pkgs/operator-core/src/operator_core/providers/openai/tests/client.test.py pkgs/operator-core/src/operator_core/tests/agent.test.py -q`
Expected: FAIL with missing provider classes or client helpers at the new path.

- [ ] **Step 3: Write the minimal implementation**

Move plain OpenAI client creation and provider assembly into `client.py`, and keep the OAuth-backed provider implementation in `oauth.py`.

```python
def get_openai_client(*, api_key: str | None, base_url: str | None) -> AsyncOpenAI:
    return AsyncOpenAI(api_key=api_key, base_url=base_url)


@define(kw_only=True)
class OpenAIModelProvider(BaseOpenAIModelProvider[OpenAIModelConfig]):
    openai_client: AsyncOpenAI


@define(kw_only=True)
class OpenAIOAuthModelProvider(BaseOpenAIModelProvider[OpenAIModelConfig]):
    store: OpenAIOAuthStore
```

Rewrite imports off `operator_core.openai_client` in the same slice and delete the old package once nothing imports it.

- [ ] **Step 4: Run the focused tests to verify they pass**

Run: `uv run pytest pkgs/operator-core/src/operator_core/providers/openai/tests/client.test.py pkgs/operator-core/src/operator_core/tests/agent.test.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add pkgs/operator-core/src/operator_core/providers/openai pkgs/operator-core/src/operator_core/tests/agent.test.py
git commit -m "refactor: move OpenAI client and provider classes"
```

### Task 6: Replace `agent.py` with the runtime package in the same slice

**Files:**

- Delete: `pkgs/operator-core/src/operator_core/agent.py`
- Create: `pkgs/operator-core/src/operator_core/agent/__init__.py`
- Create: `pkgs/operator-core/src/operator_core/agent/main.py`
- Create: `pkgs/operator-core/src/operator_core/agent/types.py`
- Create: `pkgs/operator-core/src/operator_core/agent/errors.py`
- Create: `pkgs/operator-core/src/operator_core/agent/tests/main.test.py`
- Modify: `pkgs/operator-core/src/operator_core/session.py`
- Delete: `pkgs/operator-core/src/operator_core/tests/agent.test.py`

- [ ] **Step 1: Write the failing tests**

Move the remaining runtime tests out of `pkgs/operator-core/src/operator_core/tests/agent.test.py` into `pkgs/operator-core/src/operator_core/agent/tests/main.test.py`, then delete the legacy test file in the same slice. Import the internal package modules directly during the red phase so the failure depends on the missing package layout rather than the still-existing flat module.

```python
from operator_core.agent.main import OperatorAgent
from operator_core.agent.types import OperatorSession
from operator_core.providers.openai import OpenAIModelConfig, OpenAIModelProvider


def test_operator_agent_builds_agent_with_selected_provider(tmp_path: Path) -> None:
    agent = OperatorAgent[OpenAIModelConfig, BaseModel, SampleForm](
        provider=OpenAIModelProvider(openai_client=AsyncOpenAI(api_key="test-api-key")),
        output_type=SampleForm,
        model_config=OpenAIModelConfig(name="gpt-4.1"),
    )
    assert isinstance(agent.agent.model, OpenAIChatModel)
```

- [ ] **Step 2: Run the focused tests to verify they fail**

Run: `uv run pytest pkgs/operator-core/src/operator_core/agent/tests/main.test.py -q`
Expected: FAIL because `operator_core.agent.main` and `operator_core.agent.types` do not exist until the package replaces the flat module.

- [ ] **Step 3: Write the minimal implementation**

Delete `pkgs/operator-core/src/operator_core/agent.py` and create the runtime-only `agent/` package in the same change so there is never a file/package collision.

```python
@define(kw_only=True)
class OperatorAgent[ConfigType: BaseModel, InType: BaseModel, OutType: BaseModel]:
    provider: ModelProvider[ConfigType]
    output_type: type[OutType]
    model_config: ConfigType
    agent: Agent[None, OutType] = field(init=False)
```

Move `OperatorSession` into `pkgs/operator-core/src/operator_core/agent/types.py` only if it still exists after the import rewrite.

- [ ] **Step 4: Run the focused tests to verify they pass**

Run: `uv run pytest pkgs/operator-core/src/operator_core/agent/tests/main.test.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add pkgs/operator-core/src/operator_core/agent pkgs/operator-core/src/operator_core/session.py
git commit -m "refactor: replace flat agent module with runtime package"
```

### Task 7: Replace `openai_auth` with `auth` in the same slice

**Files:**

- Delete: `pkgs/operator-cli/src/operator_cli/openai_auth/__init__.py`
- Delete: `pkgs/operator-cli/src/operator_cli/openai_auth/main.py`
- Delete: `pkgs/operator-cli/src/operator_cli/openai_auth/types.py`
- Delete: `pkgs/operator-cli/src/operator_cli/openai_auth/errors.py`
- Delete: `pkgs/operator-cli/src/operator_cli/openai_auth/utils.py`
- Create: `pkgs/operator-cli/src/operator_cli/auth/__init__.py`
- Create: `pkgs/operator-cli/src/operator_cli/auth/main.py`
- Create: `pkgs/operator-cli/src/operator_cli/auth/types.py`
- Create: `pkgs/operator-cli/src/operator_cli/auth/openai_oauth.py`
- Create: `pkgs/operator-cli/src/operator_cli/auth/tests/main.test.py`
- Create: `pkgs/operator-cli/src/operator_cli/auth/tests/openai_oauth.test.py`
- Delete: `pkgs/operator-cli/src/operator_cli/openai_auth/tests/openai_auth.test.py`
- Modify: `pkgs/operator-cli/src/operator_cli/tests/main.test.py`
- Modify: `pkgs/operator-cli/src/operator_cli/main.py`

- [ ] **Step 1: Write the failing tests**

Move the durable CLI auth tests out of `pkgs/operator-cli/src/operator_cli/openai_auth/tests/openai_auth.test.py` into `pkgs/operator-cli/src/operator_cli/auth/tests/`, then delete the legacy test file in the same slice. Rewrite `pkgs/operator-cli/src/operator_cli/tests/main.test.py` so it targets the final package imports.

```python
from operator_cli.auth.main import run_openai_login, run_openai_logout, run_openai_status
from operator_cli.auth.openai_oauth import build_openai_oauth_provider, parse_callback_url
from operator_cli.auth.types import CallbackPayload, CallbackParseError, LoginFlowDependencies
```

- [ ] **Step 2: Run the focused tests to verify they fail**

Run: `uv run pytest pkgs/operator-cli/src/operator_cli/auth/tests/main.test.py pkgs/operator-cli/src/operator_cli/auth/tests/openai_oauth.test.py pkgs/operator-cli/src/operator_cli/tests/main.test.py -q`
Expected: FAIL with missing CLI auth symbols at the new package path until the move is wired up.

- [ ] **Step 3: Write the minimal implementation**

Delete the flat `openai_auth` package and create `auth/` in the same slice so imports move directly to the final tree. Keep the auth-specific error classes in `auth/types.py` because the approved layout intentionally omits `auth/errors.py`.

```python
class OpenAIAuthCliError(RuntimeError):
    """Base error for CLI-facing OpenAI auth failures."""


class CallbackParseError(ValueError, OpenAIAuthCliError):
    """Raised when a pasted callback URL cannot be parsed safely."""


@define(frozen=True, kw_only=True)
class LoginFlowDependencies:
    listener_factory: CallbackListenerFactory
    browser_open: BrowserOpen
    exchange_code: ExchangeAuthorizationCode
    input_text: InputText
    output: Output
    state_factory: StateFactory
    timeout_seconds: int
```

- [ ] **Step 4: Run the focused tests to verify they pass**

Run: `uv run pytest pkgs/operator-cli/src/operator_cli/auth/tests/main.test.py pkgs/operator-cli/src/operator_cli/auth/tests/openai_oauth.test.py pkgs/operator-cli/src/operator_cli/tests/main.test.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add pkgs/operator-cli/src/operator_cli/auth pkgs/operator-cli/src/operator_cli/main.py pkgs/operator-cli/src/operator_cli/tests/main.test.py
git commit -m "refactor: replace flat CLI auth package"
```

### Task 8: Final import sweep and repository verification

**Files:**

- Modify: remaining imports across `pkgs/operator-core/src/**` and `pkgs/operator-cli/src/**`
- Delete: any now-empty legacy test files or `__pycache__`-only directories left behind by the moved packages

- [ ] **Step 1: Use the already-moved durable tests as the final failing signal**

Add no new migration-only tests. Instead, ensure every remaining source file and durable test imports only the final package paths.

- [ ] **Step 2: Run the full verification target before the final cleanup is complete**

Run: `just check`
Expected: FAIL until the last stale imports, dead files, and package exports are removed.

- [ ] **Step 3: Write the minimal implementation**

Delete any leftover empty test files, remove stale imports, and make every `__init__.py` export only the new package structure.

```python
from operator_core.agent import OperatorAgent
from operator_core.providers.openai import OpenAIOAuthModelProvider
from operator_core.providers.utils.store import JsonCredentialStore
from operator_shared.forms import BaseForm
from operator_cli.auth.main import run_openai_login
```

- [ ] **Step 4: Run the full verification target to verify it passes**

Run: `just check`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add pkgs/operator-core/src/operator_core pkgs/operator-core/src/operator_shared pkgs/operator-cli/src/operator_cli docs/superpowers/specs/2026-03-25-module-structure-refactor-design.md docs/superpowers/plans/2026-03-25-recursive-module-structure-refactor.md
git commit -m "refactor: adopt recursive module structure"
```

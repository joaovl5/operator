from typing import TYPE_CHECKING

import pytest
from openai import AsyncOpenAI
from pydantic import BaseModel, ValidationError
from pydantic_ai.models.openai import OpenAIChatModel, OpenAIResponsesModel

from operator_core.agent import (
    BaseForm,
    ModelConfig,
    OpenAIModelProvider,
    OpenAIModelSettings,
    OpenAIOAuthModelProvider,
    OperatorAgent,
    Permission,
    PermissionItem,
    TemporalScope,
)
from operator_core.openai_client import (
    OpenAIOAuthModelConstraintError,
    OpenAIOAuthSettingsConstraintError,
)
from operator_core.openai_store import OpenAIOAuthStore

if TYPE_CHECKING:
    from pathlib import Path


class SampleForm(BaseForm):
    value: str


def make_oauth_store(tmp_path: Path) -> OpenAIOAuthStore:
    """Create an OAuth store for provider tests."""
    return OpenAIOAuthStore(path=tmp_path / "openai.json")


def test_model_config_validates_settings_as_base_model() -> None:
    """Model settings validate through a serializable BaseModel payload."""
    config = ModelConfig.model_validate(
        {
            "name": "gpt-4.1",
            "settings": {"openai_store": True},
        }
    )

    assert isinstance(config.settings, OpenAIModelSettings)
    assert issubclass(OpenAIModelSettings, BaseModel)
    assert config.settings.model_dump(exclude_none=True) == {"openai_store": True}

    with pytest.raises(ValidationError, match="not_a_real_setting"):
        _ = OpenAIModelSettings.model_validate({"not_a_real_setting": True})


def test_openai_oauth_provider_raises_dedicated_error_for_unsupported_models(
    tmp_path: Path,
) -> None:
    """OAuth provider rejects unsupported model names with a focused error."""
    provider = OpenAIOAuthModelProvider(store=make_oauth_store(tmp_path))

    with pytest.raises(OpenAIOAuthModelConstraintError, match=r"gpt-4\.1"):
        _ = provider.build_model(model_config=ModelConfig(name="gpt-4.1"))


def test_openai_oauth_provider_raises_dedicated_error_for_forbidden_settings(
    tmp_path: Path,
) -> None:
    """OAuth provider rejects disallowed responses settings with a focused error."""
    provider = OpenAIOAuthModelProvider(store=make_oauth_store(tmp_path))

    with pytest.raises(OpenAIOAuthSettingsConstraintError, match="openai_store"):
        _ = provider.build_model(
            model_config=ModelConfig(
                name="gpt-5.3-codex",
                settings=OpenAIModelSettings(openai_store=True),
            )
        )


def test_openai_oauth_provider_builds_responses_models_from_settings_model(tmp_path: Path) -> None:
    """OAuth provider still builds responses models from validated settings objects."""
    provider = OpenAIOAuthModelProvider(store=make_oauth_store(tmp_path))

    model = provider.build_model(model_config=ModelConfig(name="gpt-5.3-codex"))

    assert isinstance(model, OpenAIResponsesModel)
    assert model.settings is not None
    assert dict(model.settings.items())["openai_store"] is False


def test_openai_and_oauth_providers_build_public_model_types(tmp_path: Path) -> None:
    """Plain OpenAI providers build chat models while OAuth providers build responses models."""
    openai_model = OpenAIModelProvider(
        openai_client=AsyncOpenAI(api_key="test-api-key")
    ).build_model(
        model_config=ModelConfig(
            name="gpt-4.1",
            temperature=0.7,
            settings=OpenAIModelSettings(openai_store=True),
        )
    )
    oauth_model = OpenAIOAuthModelProvider(store=make_oauth_store(tmp_path)).build_model(
        model_config=ModelConfig(name="gpt-5.3-codex")
    )

    assert isinstance(openai_model, OpenAIChatModel)
    assert openai_model.settings is not None
    assert dict(openai_model.settings.items())["openai_store"] is True
    assert isinstance(oauth_model, OpenAIResponsesModel)


def test_operator_agent_builds_agent_with_selected_provider(tmp_path: Path) -> None:
    """OperatorAgent exposes the model built by the selected public provider."""
    oauth_agent = OperatorAgent[BaseModel, SampleForm](
        provider=OpenAIOAuthModelProvider(store=make_oauth_store(tmp_path)),
        output_type=SampleForm,
        model_config=ModelConfig(name="gpt-5.3-codex"),
    )
    openai_agent = OperatorAgent[BaseModel, SampleForm](
        provider=OpenAIModelProvider(openai_client=AsyncOpenAI(api_key="test-api-key")),
        output_type=SampleForm,
        model_config=ModelConfig(name="gpt-4.1"),
    )

    assert isinstance(oauth_agent.agent.model, OpenAIResponsesModel)
    assert isinstance(openai_agent.agent.model, OpenAIChatModel)


def test_base_form_to_markdown_stays_explicitly_unimplemented() -> None:
    """The markdown WIP stays safe by failing explicitly instead of partially rendering."""
    form = SampleForm(value="hello")

    with pytest.raises(NotImplementedError, match="to_markdown"):
        _ = form.to_markdown()


def test_temporal_scope_session_is_accepted_as_a_safe_placeholder() -> None:
    """The unfinished session scope remains valid in permission payloads."""
    permission_item = PermissionItem(
        permission=Permission.Subagent(),
        temporal_scope=TemporalScope.Session(),
    )

    assert isinstance(permission_item.temporal_scope, TemporalScope.Session)

import pytest
from pydantic import BaseModel, ValidationError

from operator_core.providers import ModelConfig
from operator_core.providers.openai.oauth.settings import (
    OpenAIOAuthModelConfig,
    OpenAIOAuthModelSettings,
    oauth_responses_settings,
)
from operator_core.providers.openai.types import DirectOpenAIModelConfig, OpenAIModelSettings


def test_openai_model_config_validates_settings_as_base_model() -> None:
    """OpenAI settings validate through a serializable BaseModel payload."""
    config = DirectOpenAIModelConfig.model_validate(
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


def test_openai_oauth_model_settings_are_strictly_oauth_safe() -> None:
    """OAuth settings stay narrow enough to reject unsupported state."""
    settings = OpenAIOAuthModelSettings.model_validate({})

    assert isinstance(settings, BaseModel)
    assert settings.model_dump(exclude_none=True) == {
        "openai_store": False,
        "openai_send_reasoning_ids": False,
    }
    assert oauth_responses_settings() == settings

    with pytest.raises(ValidationError, match="openai_store"):
        _ = OpenAIOAuthModelSettings.model_validate({"openai_store": True})
    with pytest.raises(ValidationError, match="openai_previous_response_id"):
        _ = OpenAIOAuthModelSettings.model_validate(
            {"openai_previous_response_id": "previous-response-id"}
        )


def test_openai_oauth_model_config_rejects_unsupported_model_names() -> None:
    """OAuth model configs only admit the validated codex model name."""
    config = OpenAIOAuthModelConfig.model_validate({"name": "gpt-5.3-codex"})

    assert isinstance(config.settings, OpenAIOAuthModelSettings)
    assert config.settings == OpenAIOAuthModelSettings()

    with pytest.raises(ValidationError, match=r"gpt-4\.1"):
        _ = OpenAIOAuthModelConfig.model_validate({"name": "gpt-4.1"})


def test_provider_model_config_accepts_openai_settings_subclasses() -> None:
    """Provider-agnostic configs still carry OpenAI settings instances."""
    config = ModelConfig(name="gpt-4.1", settings=OpenAIModelSettings(openai_store=True))

    assert isinstance(config.settings, OpenAIModelSettings)
    assert config.settings.openai_store is True

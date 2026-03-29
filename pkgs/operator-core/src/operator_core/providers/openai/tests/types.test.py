import pytest
from pydantic import BaseModel, ValidationError

from operator_core.providers import ModelConfig
from operator_core.providers.openai.types import OpenAIModelConfig, OpenAIModelSettings


def test_openai_model_config_validates_settings_as_base_model() -> None:
    """OpenAI settings validate through a serializable BaseModel payload."""
    config = OpenAIModelConfig.model_validate(
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


def test_openai_model_config_validates_openai_settings_payloads() -> None:
    """OpenAI config keeps durable OpenAI settings validation local."""
    config = OpenAIModelConfig.model_validate(
        {
            "name": "gpt-5.3-codex",
            "settings": {
                "openai_store": False,
                "openai_send_reasoning_ids": False,
            },
        }
    )

    assert config.settings == OpenAIModelSettings(
        openai_store=False,
        openai_send_reasoning_ids=False,
    )


def test_provider_model_config_accepts_openai_settings_subclasses() -> None:
    """Provider-agnostic configs still carry OpenAI settings instances."""
    config = ModelConfig(name="gpt-4.1", settings=OpenAIModelSettings(openai_store=True))

    assert isinstance(config.settings, OpenAIModelSettings)
    assert config.settings.openai_store is True

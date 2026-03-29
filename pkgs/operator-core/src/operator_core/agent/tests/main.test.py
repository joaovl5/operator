from typing import TYPE_CHECKING, get_args, get_origin, get_type_hints, override

from pydantic import BaseModel
from pydantic_ai import Agent
from pydantic_ai.models import Model

import operator_core.agent.main as agent_main_module
from operator_core.agent import OperatorAgent
from operator_core.providers import ModelProvider

if TYPE_CHECKING:
    from pydantic_ai.messages import ModelMessage, ModelResponse
    from pydantic_ai.models import ModelRequestParameters


class SampleOutput(BaseModel):
    value: str


class FakeConfig(BaseModel):
    name: str


class FakeModel(Model):
    def __init__(self, *, model_name: str) -> None:
        """Store a deterministic model name for runtime-agent tests."""
        super().__init__()
        self._model_name: str = model_name

    @override
    async def request(
        self,
        messages: list[ModelMessage],
        model_settings: object,
        model_request_parameters: ModelRequestParameters,
    ) -> ModelResponse:
        """Raise because runtime-agent tests never execute model requests."""
        del messages, model_settings, model_request_parameters
        raise NotImplementedError

    @property
    @override
    def model_name(self) -> str:
        """Return the stored fake model name."""
        return self._model_name

    @property
    @override
    def system(self) -> str:
        """Return a stable provider label for the fake model."""
        return "test"


class FakeProvider(ModelProvider[FakeConfig]):
    def __init__(self) -> None:
        """Collect configs passed to `build_model`."""
        self.seen_configs: list[FakeConfig] = []

    @override
    def build_model(self, *, model_config: FakeConfig) -> Model:
        """Build a fake model and record the config used."""
        self.seen_configs.append(model_config)
        return FakeModel(model_name=model_config.name)


def test_operator_agent_builds_the_model_from_the_selected_provider() -> None:
    """OperatorAgent delegates model construction to the selected provider."""
    provider = FakeProvider()
    config = FakeConfig(name="fake-model")

    operator_agent = OperatorAgent[SampleOutput, FakeConfig](
        provider=provider,
        output_type=SampleOutput,
        model_config=config,
    )

    assert provider.seen_configs == [config]
    assert isinstance(operator_agent.agent, Agent)


def test_agent_main_annotations_are_runtime_usable() -> None:
    """OperatorAgent exposes runtime-safe annotations from the package module."""
    type_hints = get_type_hints(agent_main_module.OperatorAgent)

    assert not hasattr(agent_main_module, "_MODEL_PROVIDER_CLASS")
    assert get_origin(type_hints["provider"]) is ModelProvider
    assert get_args(type_hints["provider"])[0].__name__ == "ConfigT"
    assert get_origin(type_hints["output_type"]) is type
    assert get_args(type_hints["output_type"])[0].__name__ == "OutType"
    assert type_hints["model_config"].__name__ == "ConfigT"

from abc import ABC, abstractmethod
from collections.abc import Callable, Iterable
from enum import StrEnum
from textwrap import dedent
from typing import Final, override

from attrs import Factory, define


class PromptTraitType(StrEnum):
  """Defines which layer prompt should go, or how it should be
  used."""

  ROOT_PROMPT = "root-prompt"
  """Core harness prompt.

    It should:
        - situate agent in harness
        - display _core_ capabilities (least prone to overrides in
          session)
          - file operations
          - question tooling
          - (maybe) cross-agent comms
    """

  AGENT_PROMPT = "agent-prompt"
  """Agent archetype/override prompt.

    It should:
        - define agent-specific directives (exploration/planning/...)
        - state agent-specific capabilities
    """


@define
class PromptTrait:
  trait_type: PromptTraitType
  trait_name: str


@define
class PromptTraitRegistry:
  """Registry for defining prompt traits."""

  _traits: dict[str, PromptTrait] = Factory(dict[str, PromptTrait])

  def get_trait_key(
    self,
    trait: PromptTrait,
  ):
    """Gets unique trait key."""
    return f"{trait.trait_type.value}/{trait.trait_name}"

  def register(
    self,
    trait: PromptTrait,
  ) -> str:
    """Register trait."""
    key = self.get_trait_key(trait)
    if key in self._traits:
      msg = f"Trait with same key `{key}` already in registry!"
      raise ValueError(msg)
    self._traits[key] = trait
    return key

  def list_by_type(
    self,
    trait_type: PromptTraitType,
  ) -> list[PromptTrait]:
    """Gets all traits of a type."""
    return [
      x for x in self._traits.values() if x.trait_type == trait_type
    ]

  def get(
    self,
    trait: str | tuple[str, str],
  ) -> PromptTrait | None:
    """Gets a specific trait.

    If argument is a string, assumes is a key.
    If argument is a tuple of (str, str), assumes is a type/name pair.
    """
    if isinstance(trait, str):
      return self._traits.get(trait)
    trait_type, trait_name = trait
    return (
      filtered.pop()
      if len(
        filtered := [
          x
          for x in self._traits.values()
          if x.trait_type == trait_type and x.trait_name == trait_name
        ]
      )
      > 0
      else None
    )


class BasePrompt(ABC):
  """Prompt-like protocol."""

  trait_registry: PromptTraitRegistry

  def __init__(self, *, trait_registry: PromptTraitRegistry) -> None:
    """Initialize prompt."""
    self.trait_registry = trait_registry
    self._post_init()

  def _post_init(self) -> None:
    return

  @property
  @abstractmethod
  def identifier(self) -> str:
    """Identifier for distinguishing prompt."""

  @property
  @abstractmethod
  def trait(self) -> PromptTrait:
    """Gets the prompt trait."""

  @abstractmethod
  def render(self, **_kwargs: object) -> str:
    """Render the prompt."""


def bake_prompt(
  identifier: str,
  trait: str | tuple[str, str],
  rendering: str | Callable[[], str],
) -> type[BasePrompt]:
  """Generate a BasePrompt-abiding class."""

  class BakedPrompt(BasePrompt):
    @property
    @override
    def identifier(self) -> str:
      return identifier

    @property
    @override
    def trait(self) -> PromptTrait:
      x = self.trait_registry.get(trait)
      if not x:
        msg = f"Expected trait `{trait}` but it's not in registry!"
        raise ValueError(msg)
      return x

    @override
    def render(self, **_kwargs: object) -> str:
      x = rendering if isinstance(rendering, str) else rendering()
      return dedent(x)

  return BakedPrompt


@define
class PromptRegistry:
  """Registry for prompts."""

  trait_registry: PromptTraitRegistry
  _prompts: dict[str, BasePrompt] = Factory(dict[str, BasePrompt])

  def get_prompt_key(self, prompt: BasePrompt) -> str:
    """Gets unique prompt key."""
    return (
      f"{self.trait_registry.get_trait_key(prompt.trait)}/"
      f"{prompt.identifier}"
    )

  def register(self, p_type: type[BasePrompt]) -> str:
    """Register prompt-like type."""
    p = p_type(trait_registry=self.trait_registry)
    p_key = self.get_prompt_key(p)
    if p_key in self._prompts:
      msg = f"Prompt key `{p_key}` already in registry!"
      raise ValueError(msg)
    self._prompts[p_key] = p
    return p_key

  def register_many(
    self,
    *p_types: type[BasePrompt] | Iterable[type[BasePrompt]],
  ) -> list[str]:
    """Register multiple prompt-like types."""
    out: list[str] = []
    for x in p_types:
      if not isinstance(x, Iterable):
        out.append(self.register(x))
        continue
      out.extend(self.register(y) for y in x)
    return out

  def get(self, k: str) -> BasePrompt | None:
    """Gets prompt by its key."""
    return self._prompts.get(k)


PROMPT_TRAIT_REGISTRY: Final = PromptTraitRegistry()
PROMPT_REGISTRY: Final = PromptRegistry(
  trait_registry=PROMPT_TRAIT_REGISTRY
)

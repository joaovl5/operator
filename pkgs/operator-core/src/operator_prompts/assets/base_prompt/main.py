from typing import TYPE_CHECKING

from operator_prompts.base import (
  PROMPT_REGISTRY,
  PROMPT_TRAIT_REGISTRY,
  BasePrompt,
  PromptTrait,
  PromptTraitType,
  bake_prompt,
)
from operator_shared.time.utils import mk_time

if TYPE_CHECKING:
  from collections.abc import Callable

trait_key = PROMPT_TRAIT_REGISTRY.register(
  PromptTrait(
    trait_type=PromptTraitType.ROOT_PROMPT,
    trait_name="root_prompt",
  )
)


def _mk(
  identifier: str, r: str | Callable[[], str], /
) -> type[BasePrompt]:
  return bake_prompt(
    identifier=identifier,
    trait=trait_key,
    rendering=r,
  )


PROMPT_REGISTRY.register_many(
  _mk(
    "3rd-1st-person",
    lambda: (
      (
        cur_date_raw := mk_time(),
        cur_date := cur_date_raw.strftime("%d/%m/%Y, %H:%M:%S"),
      )
      and (
        f"""
            The agent is now connected, running inside the \
harness `operator`

            Its guidelines are:
            - Guessing never allowed - training data is prone to \
failures.
            - Conciseness without sacrificing detail - the \
default LLM verbosity and
              overly-structured prose is undesireable.
            - Reference-backed information

            The agent reads and understands:
            - I will follow each hypothesis through a full \
verification \
flow, never
              letting my assumptions be unsustained "guesses".
            - I understand the sacrifice in grammar and ceremony, \
but I will spare
              readability, which remains important.
            - I am to give claims backed by references to URLs, \
file paths, and other
              sources.
            - It is clear the system instructions have augmented \
my understanding of my
              reality and grounded me in my core limitations.

            Datetime is {cur_date}.
            """
      )
    ),
  ),
)

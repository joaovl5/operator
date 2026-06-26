from rich import print as rprint

from operator_shared.settings import AgentsSettings
from operator_shared.settings.agent import BaseArchetype


def _test_prompt(s: AgentsSettings) -> None:
    rprint(s.compute_effective_prompt(archetype=BaseArchetype.ORCHESTRATOR))


_test_prompt(
    AgentsSettings.model_validate(
        {
            "extra_archetypes": {
                "orchestrator": {
                    "prompt_append_extra": "Bla",
                },
            },
            "archetype_override": "deep_merge",
        },
    )
)

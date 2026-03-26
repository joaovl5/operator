from operator_core.toolsets import Toolset, ToolsetAction
from operator_shared.forms import BaseForm, ObjectMetadata


class InputForm(BaseForm):
    value: str


class OutputForm(BaseForm):
    result: str


def test_toolset_serializes_public_schema_payloads() -> None:
    """Toolsets keep metadata and action schemas serializable as public payloads."""
    action = ToolsetAction[InputForm, OutputForm](
        metadata=ObjectMetadata(
            name="lookup",
            description="Run a lookup",
            detail="Uses the shared lookup pipeline.",
        ),
        input_model=InputForm(value="query"),
        output_model=OutputForm(result="answer"),
    )
    toolset = Toolset[InputForm, OutputForm](
        metadata=ObjectMetadata(
            name="search",
            description="Search tools",
            detail="Groups lookup actions for search tasks.",
        ),
        actions=[action],
    )

    assert toolset.to_json() == {
        "metadata": {
            "name": "search",
            "description": "Search tools",
            "detail": "Groups lookup actions for search tasks.",
        },
        "actions": [
            {
                "metadata": {
                    "name": "lookup",
                    "description": "Run a lookup",
                    "detail": "Uses the shared lookup pipeline.",
                },
                "input_model": {"value": "query"},
                "output_model": {"result": "answer"},
            }
        ],
    }

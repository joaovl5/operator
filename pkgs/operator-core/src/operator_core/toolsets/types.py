from operator_shared.forms import BaseForm, ObjectMetadata


class ToolsetAction[InType: BaseForm, OutType: BaseForm](BaseForm):
    """A toolset action schema pair with metadata."""

    metadata: ObjectMetadata
    input_model: InType
    output_model: OutType


class Toolset[InType: BaseForm, OutType: BaseForm](BaseForm):
    """Toolset for agent usage."""

    metadata: ObjectMetadata
    actions: list[ToolsetAction[InType, OutType]]

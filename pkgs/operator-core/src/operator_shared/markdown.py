from typing import Any, Protocol

from attrs import define


@define
class MarkdownRenderState:
    heading_level: int = 1
    inside_list: bool = False
    list_index: int = 0  # when inside_list


class BaseMarkdownNode(Protocol):
    """Protocol for nodes that can render themselves as Markdown."""

    def render(self, state: MarkdownRenderState) -> str:
        """Render the node using the provided markdown state."""
        ...


class UnsupportedMarkdownValueError(TypeError):
    """Raised when `to_markdown` receives a value it cannot represent."""


def _render_list_item(value: str, state: MarkdownRenderState) -> str:
    """Render a scalar value, preserving list numbering when needed."""
    list_prefix = f"{state.list_index}. " if state.inside_list else ""
    return f"{list_prefix}{value}"


class MarkdownNode:
    type ModelUnion[T: BaseMarkdownNode] = T

    @define
    class Heading:
        """A heading with nested child content."""

        title: str
        content: list[MarkdownNodeType]

        def render(self, state: MarkdownRenderState) -> str:
            """Render the heading and its children at the next heading level."""
            list_prefix = f"{state.list_index}." if state.inside_list else ""
            heading_prefix = ("#" * state.heading_level) + f" {list_prefix}"
            return "\n".join(
                [
                    f"{heading_prefix} {self.title}\n\n",
                    *[
                        x.render(
                            state=MarkdownRenderState(
                                heading_level=state.heading_level + 1,
                                inside_list=False,
                            )
                        )
                        for x in self.content
                    ],
                ]
            )

    @define
    class Paragraph:
        """A plain text paragraph."""

        content: str

        def render(self, state: MarkdownRenderState) -> str:
            """Render paragraph text, adding a list prefix when nested in a list."""
            return _render_list_item(self.content, state)

    @define
    class List:
        """An ordered list of markdown nodes."""

        content: list[MarkdownNodeType]

        def render(self, state: MarkdownRenderState) -> str:
            """Render child nodes as an ordered list."""
            parent_list_prefix = "\t" if state.inside_list else ""

            return "\n".join(
                [
                    parent_list_prefix
                    + x.render(
                        state=MarkdownRenderState(
                            heading_level=state.heading_level,
                            inside_list=True,
                            list_index=i,
                        )
                    )
                    for i, x in enumerate(self.content, start=1)
                ],
            )

    # special nodes:

    @define
    class Number:
        """A numeric scalar value."""

        value: float | int

        def render(self, state: MarkdownRenderState) -> str:
            """Render the numeric value as text."""
            return _render_list_item(str(self.value), state)

    @define
    class Toggle:
        """A boolean scalar value."""

        value: bool

        def render(self, state: MarkdownRenderState) -> str:
            """Render the boolean value as lowercase text."""
            return _render_list_item(str(self.value).lower(), state)

    @define
    class Null:
        """A null scalar value."""

        def render(self, state: MarkdownRenderState) -> str:
            """Render a null value as explicit placeholder text."""
            return _render_list_item("null", state)


type MarkdownNodeType = MarkdownNode.ModelUnion[
    MarkdownNode.Heading
    | MarkdownNode.Paragraph
    | MarkdownNode.List
    | MarkdownNode.Number
    | MarkdownNode.Toggle
    | MarkdownNode.Null
]


def to_markdown(obj: Any) -> MarkdownNodeType:
    """Convert basic Python data into the conservative markdown node tree."""
    match obj:
        case dict(dict_obj):
            return MarkdownNode.List(
                content=[
                    MarkdownNode.Heading(title=k, content=[to_markdown(v)])
                    for k, v in dict_obj.items()
                ],
            )
        case list(list_obj):
            return MarkdownNode.List(
                content=[to_markdown(v) for v in list_obj],
            )
        case str(str_obj):
            return MarkdownNode.Paragraph(content=str_obj)
        case bool(bool_obj):
            return MarkdownNode.Toggle(value=bool_obj)
        case float(x) | int(x):
            return MarkdownNode.Number(value=x)
        case None:
            return MarkdownNode.Null()
        case _:
            message = f"Unsupported value for markdown conversion: {type(obj).__name__}"
            raise UnsupportedMarkdownValueError(message)

from typing import Any

from pydantic import BaseModel, Field


class ObjectMetadata(BaseModel):
  """Metadata for objects sharing a common pattern."""

  name: str = Field(description="Short name, used as its identifier.")
  description: str = Field(
    description="Brief summary telling when to use the it."
  )
  detail: str = Field(
    description=(
      "Comprehensive text on procedures, comments, etc. for "
      "understanding "
      "and handling the information. May describe: best practices, "
      "bad patterns, "
      "object-specific instructions or comments, etc."
    ),
  )


class BaseForm(BaseModel):
  """Wrapper for BaseModel with utility functions."""

  def to_json(self) -> dict[str, Any]:
    """Convert instance to a JSON-safe dictionary."""
    return self.model_dump(
      mode="json",
      warnings="error",
    )

  def get_title(self) -> str:
    """Get this object's title for usage in other places."""
    return self.__repr_name__()

  def to_markdown(self) -> str:
    """Transform the serialized form of the object into Markdown."""
    message = "BaseForm.to_markdown is not implemented yet"
    raise NotImplementedError(message)

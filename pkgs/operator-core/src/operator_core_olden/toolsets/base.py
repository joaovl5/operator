from abc import ABC, abstractmethod

from pydantic_ai.tools import ToolFuncPlain

type ToolsetPydanticExport = list[ToolFuncPlain[...]]


class BaseToolset(ABC):
  """Toolset base class."""

  @abstractmethod
  def export_to_pydantic(self) -> ToolsetPydanticExport:
    """Export toolset as a list of pydantic_ai tool functions."""

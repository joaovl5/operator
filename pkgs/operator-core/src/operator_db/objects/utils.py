from typing import override

from advanced_alchemy.types import JsonB
from pydantic import BaseModel
from sqlalchemy import Dialect, TypeDecorator


def poly(discriminator: str, *, root: bool = False) -> dict[str, str]:
  """Make a `__mapper_args__` polymorphic relation."""
  out = {"polymorphic_identity": discriminator}
  if root:
    out["polymorphic_on"] = "type"

  return out


class PydanticJSON[T: BaseModel](TypeDecorator[T]):
  """Store a Pydantic model as JSON."""

  impl = JsonB
  cache_ok = True

  def __init__(self, model_type: type[T]):
    """Initialize custom Pydantic field."""
    super().__init__()
    self.model_type = model_type

  @override
  def process_bind_param(
    self, value: T | None, dialect: Dialect
  ) -> object:
    if value is None:
      return None
    return value.model_dump(mode="json")

  @override
  def process_result_value(
    self, value: object, dialect: Dialect
  ) -> T | None:
    if value is None:
      return None
    return self.model_type.model_validate(value)

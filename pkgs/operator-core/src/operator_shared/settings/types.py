"""Shared typing helpers for Operator settings."""

from collections.abc import Mapping
from typing import (
  TYPE_CHECKING,
  Annotated,
  ClassVar,
  Protocol,
  TypeVar,
)

from pydantic import (
  BaseModel,
  BeforeValidator,
  ConfigDict,
  GetCoreSchemaHandler,
  GetPydanticSchema,
  StringConstraints,
)
from pydantic_core import CoreSchema, core_schema

if TYPE_CHECKING:
  from collections.abc import Callable


class SettingsBase(BaseModel):
  model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")


type Slug = Annotated[
  str,
  StringConstraints(
    strict=True,
    strip_whitespace=True,
    to_lower=True,
  ),
]


def _fac_schema(
  source_t: object, handler: GetCoreSchemaHandler
) -> CoreSchema:
  if not callable(source_t):
    msg = f"Fac[T] requires a zero-arg callable as a constructor, got {source_t!r}"
    raise TypeError(msg)
  factory: Callable[[], object] = source_t
  return core_schema.with_default_schema(
    handler(source_t),
    default_factory=factory,
    validate_default=True,
  )


T = TypeVar("T")
Fac = Annotated[
  T,
  GetPydanticSchema(_fac_schema),
]
"""Makes a field of default_factory `T`."""


def _entry_val(x: object) -> object:
  if not isinstance(x, Mapping):
    return x
  entries: dict[object, object] = {}
  for k, v in x.items():  # pyright: ignore[reportUnknownVariableType]
    if not isinstance(v, Mapping):
      entries[k] = v
      continue
    entry_data = dict(v)  # pyright: ignore[reportUnknownVariableType]
    entry_data["key"] = k
    entries[k] = entry_data
  return entries


class _EntryLike(Protocol):
  key: str


T_entry_like = TypeVar("T_entry_like", bound=_EntryLike)

Entries = Annotated[
  dict[Slug, T_entry_like],
  BeforeValidator(_entry_val),
]
"""Makes a key-value dict where its values will have their `key` field set to the
dictionary key for convenience."""

from typing import ClassVar, Literal, final

import rich
from pydantic import BaseModel

from operator_shared.settings.types import Entries, Fac, SettingsBase


class ObjI(SettingsBase):
  key: str
  name: str


class ObjL(SettingsBase):
  items: Fac[Entries[ObjI]]


def _inspect(**kwargs: BaseModel) -> None:
  for k, v in kwargs.items():
    rich.print(f"##### {k}")
    rich.print_json(v.model_dump_json())


@final
class KA(BaseModel):
  kind: ClassVar = Literal["Abc abc"]


_inspect(
  empty=ObjL.model_validate({}),
  some=ObjL.model_validate({"items": {"some": {"name": "Dude"}}}),
  ka=KA.model_validate({}),
)

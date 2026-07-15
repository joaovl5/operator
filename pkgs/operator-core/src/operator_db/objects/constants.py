from typing import Annotated, Any

from sqlalchemy import String
from sqlalchemy.orm import MappedColumn, mapped_column

TXT_SLUG = 128
TXT_SHORT = 256
TXT_MEDIUM = 1024
TXT_LARGE = 16912


def _txt(x: int) -> MappedColumn[Any]:
  return mapped_column(String(x))


type TxtSlug = Annotated[str, _txt(TXT_SLUG)]
type TxtShort = Annotated[str, _txt(TXT_SHORT)]
type TxtMedium = Annotated[str, _txt(TXT_MEDIUM)]
type TxtLarge = Annotated[str, _txt(TXT_LARGE)]

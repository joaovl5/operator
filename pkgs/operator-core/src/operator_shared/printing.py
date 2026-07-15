from typing import Any

from rich import get_console
from rich import print as rprint
from rich.pretty import Pretty

p = rprint


def pp(obj: Any) -> None:
  """Pretty-printing function."""
  cons = get_console()
  cons.print(
    Pretty(
      obj,
      margin=100,
      indent_size=2,
      indent_guides=True,
    )
  )

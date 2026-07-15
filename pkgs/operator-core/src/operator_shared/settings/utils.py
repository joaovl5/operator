"""Internal helpers for shared Operator settings loading."""

from collections.abc import Mapping
from typing import Any

type _Mapping = Mapping[Any, Any]
type _Dict = dict[Any, Any]


def deep_merge(
  x: _Mapping,
  y: _Mapping,
  *,
  erase_lists: bool = False,
) -> _Dict:
  """Deep-merge two mappings recursively, with `y` taking precedence.

  Args:
      x: Left side of merge
      y: Right side of merge.
      erase_lists: If set, will erase list conflicts instead of appending.
  """
  out = {**x}

  for k, y_v in y.items():
    x_v = out.get(k)
    if x_v is not None and y_v is None:
      continue
    if (
      # just use y_v plainly if x_v is None
      # or if either x_v/y_v isn't an iterable
      x_v is None
      or not hasattr(x_v, "__iter__")
      or not hasattr(y_v, "__iter__")
      or isinstance(y_v, str)
    ):
      out[k] = y_v
      continue
    if isinstance(x_v, Mapping):
      if not isinstance(y_v, Mapping):
        out[k] = y_v
        continue
      out[k] = deep_merge(x_v, y_v)
      continue

    # if we're here, both x_v and y_v are list-like
    # for simplicity of this implementation, we will just
    # assume both of them *are* lists
    if erase_lists:
      out[k] = y_v
      continue
    lst = []
    lst.extend(i for i in x_v)
    lst.extend(i for i in y_v)
    out[k] = lst

  return out

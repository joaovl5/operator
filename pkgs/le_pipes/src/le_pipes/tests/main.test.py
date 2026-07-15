from typing import Any

from le_pipes.builtins import collect, size, take, where
from le_pipes.utils import is_iterable

sampl = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]


def test_where():
  """Test `where` works."""
  even = sampl | where(int, lambda x: x % 2 == 0)

  assert len(sampl) == 10
  assert len(list(even)) == 5

  mix = ["ABC", True, (1, 2, 3), 5, b"1234"]
  mix_iters = mix | where(Any, is_iterable) | collect(Any)

  assert mix_iters | size == 3


def test_take():
  """Test `where` works."""
  some = sampl | take(int, 3)

  assert len(list(some)) == 3

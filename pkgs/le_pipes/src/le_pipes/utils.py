from collections.abc import Iterable
from typing import TypeIs


def is_t[T](t: type[T], x: object) -> TypeIs[T]:  # ty:ignore[invalid-type-guard-definition]  # pyright: ignore[reportGeneralTypeIssues]
    """Alias for `isinstance`."""
    return isinstance(x, t)


def is_iterable[T](x: object) -> TypeIs[Iterable[T]]:
    """Check if `x` is `Iterable`."""
    return is_t(Iterable, x)


def is_something[T](x: T | None) -> TypeIs[T]:
    """Check if `x` is not None."""
    return x is not None

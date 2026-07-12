from typing import TYPE_CHECKING, TypeIs, overload

from .base import Pipe

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Iterator, Sequence


# `w` values are required for 'type witnesses' because python type checkers are all
# stupid and we as a society cannot collectively do better than this for it and i am not
# going to rewrite all of this in a better typed language just to prove a point just yet


@Pipe
def take[T](
    iterable: Iterable[T],
    w: type[T],
    n: int,
) -> Iterator[T]:
    """Yield at most `n` items from `iter`."""
    del w
    if not n:
        return
    for i in iterable:
        yield i
        n -= 1
        if not n:
            break


@Pipe
def where[T, H](
    iterable: Iterable[T],
    w: type[H],
    # yeah its gonna be just `TypeIs` for now because overloading didnt work and i do
    # not care enough to work on this any further
    predicate: Callable[[T], TypeIs[H]],
) -> Iterator[H]:
    """Yield elements fulfilling a `predicate`."""
    del w
    return (x for x in iterable if predicate(x))


@Pipe
def holo[T, H](
    iterable: Iterable[T],
    w: type[H],
    predicate: Callable[[T], H],
) -> Iterator[H]:
    """Transform iterable via a `predicate`, a 'hologram'."""
    del w
    return (predicate(x) for x in iterable)


@Pipe
def collect[T](
    iterable: Iterable[T],
    w: type[T],
) -> list[T]:
    """Collect elements from `iterable` into a list."""
    del w
    return list(iterable)


@Pipe
def size[T](sequence: Sequence[T]) -> int:
    """Alias for `len`."""
    return len(sequence)

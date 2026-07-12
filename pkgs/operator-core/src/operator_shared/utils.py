from collections.abc import Iterable, Iterator, Mapping, Sequence
from functools import partial
from typing import TYPE_CHECKING, Any, Literal, TypeIs, overload

import yaml
from pydantic import JsonValue

from le_pipes.base import Pipe
from le_pipes.builtins import where

if TYPE_CHECKING:
    from collections.abc import Callable

    _L = Literal

type _Dict = dict[Any, Any]


def walk_dicts(x: _Dict, predicate: Callable[[_Dict], _Dict]) -> _Dict:
    """Walk recursively through dictionaries, calling predicate after children."""
    out: _Dict = {}

    for k, v in x.items():
        if isinstance(v, Mapping):
            out[k] = walk_dicts(dict(v), predicate=predicate)
        elif isinstance(v, list):
            out[k] = [
                walk_dicts(
                    dict(z),
                    predicate=predicate,
                )
                if isinstance(z, Mapping)
                else z
                for z in v
            ]
        else:
            out[k] = v

    return predicate(out)


def remove_empty(x: _Dict) -> _Dict:
    """Returns a new dictionary with empty things removed."""
    out = x.copy()
    for k, v in x.items():
        # will erase some non-truthy things (aside from bools)
        # - empty strings
        # - empty collections/iterables
        # - ...
        if not v and not isinstance(v, bool):
            del out[k]
    return out


def present_json(
    x: JsonValue,
    *,
    indent: int = 2,
    sort_keys: bool = False,
) -> str:
    """Encode a JSON in a string through some means.

    Current impl. will use YAML if value isn't scalar, otherwise will convert to string.
    """
    match x:
        case None:
            return "null"
        case str():
            return x
        case bool():
            return "true" if x else "false"
        case int() | float():
            return str(x)
        case _:
            return yaml.dump(
                x,
                indent=indent,
                sort_keys=sort_keys,
            )


def ensure[T](x: T | None) -> T:
    """Ensure `x` isn't None, error otherwise."""
    if x is None:
        msg = "Needed `x` to not be `None`"
        raise ValueError(msg)
    return x


def _check_bounds(
    x: int | None = None,
    a: int | None = None,
    b: int | None = None,
) -> bool:
    if not x:
        return True
    fail: bool = False
    if a:
        fail |= x >= a
    if b:
        fail |= x <= b
    return not fail


def ensure_n[SeqT: Sequence[Any]](
    seq: SeqT,
    *,
    n: int | Sequence[int] | None = None,
    lmin: int | None = None,
    lmax: int | None = None,
) -> SeqT:
    """Ensure `seq` abides by length constraints.

    Will throw an error if no constraints were selected in the arguments.

    Args:
        seq: Sequence to evaluate length
        n: Expected length values, disconsidered if `None`.
        lmin: Minimum (inclusive) value of length, disconsidered if `None`.
        lmax: Minimum (inclusive) value of length, disconsidered if `None`.

    """
    if not (n or lmin or lmax):
        msg = "Neither of the arguments for `ensure_n` were supplied."
        raise ValueError(msg)
    if isinstance(n, int):
        n = (n,)
    if not _check_bounds(n, lmin, lmax):
        msg = "Bounds given for argument `n` are outside those of arguments `min`/`max`."
        raise ValueError(msg)
    seq_len = len(seq)
    if (n and seq_len in n) or _check_bounds(seq_len, lmin, lmax):
        return seq
    msg = "Bounds for `seq`'s length were not abiding by params!"
    raise ValueError(msg)


@overload
def ensure_singleton[T](
    seq: Sequence[T],
    *,
    none_ok: _L[False] = False,
) -> T: ...
@overload
def ensure_singleton[T](
    seq: Sequence[T],
    *,
    none_ok: _L[True] = True,
) -> T | None: ...
def ensure_singleton[T](
    seq: Sequence[T],
    *,
    none_ok: bool = False,
) -> T | None:
    """Error if `seq` doesn't contain exactly one element, return it otherwise.

    If `none_ok` is set, will not hard-fail if sequence has no elements and will return
    `None`.
    """
    seq = ensure_n(seq, n=(0, 1) if none_ok else 1)
    if seq:
        return seq[0]
    return None


# type checkers dont like overloads for this apparently so we need to make these
# pipe-form aliases


@Pipe
def get_one_or_none[T](seq: Sequence[T] | Iterable[T]) -> T | None:
    """Pipe-form of `ensure_singleton(none_ok=True)`.

    Will consume iterable if needed.
    """
    seq = list(seq) if not isinstance(seq, Sequence) else seq

    return ensure_singleton(seq, none_ok=True)


@Pipe
def get_one[T](seq: Sequence[T] | Iterable[T]) -> T:
    """Pipe-form of `ensure_singleton(none_ok=False)`.

    Will consume iterable if needed.
    """
    seq = list(seq) if not isinstance(seq, Sequence) else seq
    return ensure_singleton(seq, none_ok=False)


def isinst[T](t: T, x: object) -> TypeIs[T]:
    """Check if `x` is instance of `t`.

    Alias for `isinstance` with arg positions reversed.
    """
    return isinstance(x, t)


def isinstp[X, T](t: T) -> Callable[[X], TypeIs[T]]:
    """Return partially-applied `instp` with `t`."""
    return partial(isinst, t)


@Pipe
def where_inst[X, T](iterable: Iterable[X], t: type[T]) -> Iterator[T]:
    """Shorthand for `where(T, isinstp(T))`."""
    return iterable | where(t, isinstp(t))

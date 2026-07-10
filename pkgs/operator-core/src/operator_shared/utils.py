from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeIs

import yaml
from pydantic import JsonValue

if TYPE_CHECKING:
    from collections.abc import Callable

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


def ensure[T](x: T | None) -> TypeIs[T]:
    """Ensure `x` isn't None, error otherwise."""
    if x is None:
        msg = "Needed `x` to not be `None`"
        raise ValueError(msg)
    return x

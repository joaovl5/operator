from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

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

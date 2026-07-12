import functools
from collections.abc import Callable
from typing import Concatenate

from attrs import define


@define(slots=False)
class Pipe[In, Out, **P]:
    """Base primitive for pipeline operations."""

    type _Fn = Callable[Concatenate[In, P], Out]

    fn: _Fn

    def __attrs_post_init__(self) -> None:
        """Handle post-init logic."""
        functools.update_wrapper(self, self.fn)

    def __call__(
        self,
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> Pipe[In, Out, []]:
        """Bind operation args without executing."""

        def configured(value: In, /) -> Out:
            return self.fn(value, *args, **kwargs)

        return Pipe(configured)

    def __ror__(
        # restrict this only for already-initialized pipes with `[]`
        self: Pipe[In, Out, []],
        value: In,
    ) -> Out:
        """Apply configured function to its left-hand value."""
        return self.fn(value)

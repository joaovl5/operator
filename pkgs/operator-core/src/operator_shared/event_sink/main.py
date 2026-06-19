"""Shared async event sink protocol."""

from typing import Protocol


class EventSink[EventT](Protocol):
    """Receives async events."""

    async def __call__(self, *, event: EventT) -> None:
        """Handle one event."""

from pydantic import BaseModel


class Communication:
    """Namespace for types handling agent communication rules."""

    class _BaseComm(BaseModel): ...

    class Deny(_BaseComm):
        """Deny communication in all cases."""

    class Allow(_BaseComm):
        """Allow communication in configured cases."""

        allow_all: bool = False  # overrides others
        allow_parent: bool = True
        allow_invoked: bool = True
        allow_downwards: bool = False
        allow_upwards: bool = False
        allow_neighbours: bool = False


type CommunicationState = Communication.Deny | Communication.Allow
"""Specifies what should happen when an agent attempts to communicate with another."""

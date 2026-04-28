"""Mail-related constants and enums."""

from enum import StrEnum


class MailMessageState(StrEnum):
    """State of a mailbox message."""

    QUEUED = "queued"
    """Message is queued and wasn't yet fetched/read."""

    READ = "read"
    """Message left queue and was already read."""

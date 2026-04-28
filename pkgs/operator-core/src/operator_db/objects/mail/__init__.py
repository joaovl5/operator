"""Mail object package."""

from operator_db.objects.mail.entity import MailboxMapping, MailMessageEnt
from operator_db.objects.mail.schema import (
    MailDeliveryResponseSchema,
    MailRequestSchema,
    MailResponseSchema,
    MailSchema,
)
from operator_db.objects.mail.service import MailService

__all__ = [
    "MailDeliveryResponseSchema",
    "MailMessageEnt",
    "MailRequestSchema",
    "MailResponseSchema",
    "MailSchema",
    "MailService",
    "MailboxMapping",
]

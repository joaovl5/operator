"""Constants shared across operator_db."""

from operator_db.constants.db import (
    DESCRIPTION_MAX_LEN,
    EXTRA_DETAIL_MAX_LEN,
    SHORT_STR_LEN,
    TITLE_MAX_LEN,
    VERY_LONG_MAX_LEN,
)
from operator_db.constants.mail import MailMessageState
from operator_db.constants.role import HistoryMessageRole

__all__ = [
    "DESCRIPTION_MAX_LEN",
    "EXTRA_DETAIL_MAX_LEN",
    "SHORT_STR_LEN",
    "TITLE_MAX_LEN",
    "VERY_LONG_MAX_LEN",
    "HistoryMessageRole",
    "MailMessageState",
]

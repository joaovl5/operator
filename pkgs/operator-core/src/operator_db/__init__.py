"""Abstracts DB-related stuff from rest of core logic."""

from operator_db.connection import (
    DatabaseConfigProtocol,
    OperatorDbConnectionError,
    OperatorDbMigrationError,
    ensure_db_ready,
    get_db_engine,
    get_db_url,
)
from operator_db.objects import (
    HistoryEnt,
    HistoryEpochEnt,
    HistoryEpochMessageEnt,
    MailboxMapping,
    MailMessageEnt,
    SessionAgentEnt,
    SessionEnt,
)
from operator_db.utils.db import Base, Entity

__all__ = [
    "Base",
    "DatabaseConfigProtocol",
    "Entity",
    "HistoryEnt",
    "HistoryEpochEnt",
    "HistoryEpochMessageEnt",
    "MailMessageEnt",
    "MailboxMapping",
    "OperatorDbConnectionError",
    "OperatorDbMigrationError",
    "SessionAgentEnt",
    "SessionEnt",
    "ensure_db_ready",
    "get_db_engine",
    "get_db_url",
]

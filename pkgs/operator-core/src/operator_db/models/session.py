"""Session-related models."""

from typing import final

from .base import Entity


@final
class SessionEnt(Entity):
    __tablename__ = "sessions"


@final
class HistoryEnt(Entity):
    __tablename__ = "histories"


@final
class HistoryEpochEnt(Entity):
    __tablename__ = "history_epochs"


@final
class HistoryEpochMessageEnt(Entity):
    __tablename__ = "history_epoch_messages"

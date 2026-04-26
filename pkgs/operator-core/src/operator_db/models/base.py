from typing import TYPE_CHECKING, ClassVar

import fastnanoid
from sqlalchemy import String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

if TYPE_CHECKING:
    from datetime import datetime


class Base(DeclarativeBase):
    pass


SHORT_STR_LEN: int = 50


class Entity(Base):
    """Abstract base for persisted entities."""

    __abstract__: ClassVar[bool] = True

    id: Mapped[str] = mapped_column(
        String(SHORT_STR_LEN),
        primary_key=True,
        default=fastnanoid.generate,
    )
    created_at: Mapped[datetime] = mapped_column(
        nullable=False,
        server_default=func.current_timestamp(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )

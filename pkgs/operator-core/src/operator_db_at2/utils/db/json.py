"""SQLAlchemy JSON type helpers."""

from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import JSONB

JSONColumn = JSON().with_variant(JSONB(), "postgresql")
"""Generic SQLAlchemy JSON type that renders as JSONB on Postgres."""

__all__ = ["JSONColumn"]

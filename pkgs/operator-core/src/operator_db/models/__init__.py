"""Handles registering models to be accessible, among other things, to Alembic migrations.

Any models made should be exported through `__init__.py`.
"""

from .base import Base, Entity

__all__ = [
    "Base",
    "Entity",
]

from typing import ClassVar
from uuid import UUID

from advanced_alchemy.base import UUIDv7AuditBase, orm_registry
from advanced_alchemy.repository import SQLAlchemyAsyncRepository
from sqlalchemy.orm import (
    registry as SQLAlchemyRegistry,  # noqa: N812, TC002
)

type IDType = UUID


class Base(UUIDv7AuditBase):
    __abstract__ = True

    registry: ClassVar[SQLAlchemyRegistry] = orm_registry


class Repo[T: Base](SQLAlchemyAsyncRepository[T]): ...

from typing import TYPE_CHECKING, Any, ClassVar, TypeVar
from uuid import UUID

from advanced_alchemy.base import UUIDv7AuditBase, orm_registry
from advanced_alchemy.repository import SQLAlchemyAsyncRepository
from advanced_alchemy.service import SQLAlchemyAsyncRepositoryService
from sqlalchemy.orm import (
    registry as SQLAlchemyRegistry,  # noqa: N812, TC002
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncAttrs, AsyncSession

    from operator_shared.settings import OperatorSettings

type IDType = UUID


class Base(UUIDv7AuditBase):
    __abstract__ = True

    registry: ClassVar[SQLAlchemyRegistry] = orm_registry

    @property
    def aw(self) -> AsyncAttrs._AsyncAttrGetitem:
        """Alias for `awaitable_attrs`."""
        return self.awaitable_attrs


class Repo[T: Base](SQLAlchemyAsyncRepository[T]): ...


type _Svc = Svc[Any]
M = TypeVar("M", bound=Base)
S = TypeVar("S", bound=_Svc)


class Svc[T: Base](SQLAlchemyAsyncRepositoryService[T]):
    _svc_cache: dict[type[_Svc], _Svc]
    _settings: OperatorSettings

    def __init__(  # noqa: D107
        self,
        *_args: Any,
        settings: OperatorSettings,
        **_kwargs: Any,
    ) -> None:
        super().__init__(*_args, **_kwargs)
        self._settings = settings

    @property
    def _session(self) -> AsyncSession:
        return self.repository.session

    def _get_svc(self, svc_cls: type[S]) -> S:
        if not hasattr(self, "_svc_cache"):
            self._svc_cache = {}

        if svc_cls not in self._svc_cache:
            self._svc_cache[svc_cls] = svc_cls(
                session=self._session,
                settings=self._settings,
            )

        svc: S = self._svc_cache[svc_cls]  # pyright: ignore[reportAssignmentType]
        return svc

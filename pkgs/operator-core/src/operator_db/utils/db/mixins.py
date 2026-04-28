from typing import Annotated

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from operator_db.constants import (
    DESCRIPTION_MAX_LEN,
    EXTRA_DETAIL_MAX_LEN,
    SHORT_STR_LEN,
    TITLE_MAX_LEN,
    VERY_LONG_MAX_LEN,
)
from operator_db.utils.db.json import JSONColumn
from operator_db.utils.json import JsonObject

ReqStr = Annotated[
    str,
    mapped_column(
        String(SHORT_STR_LEN),
        nullable=False,
    ),
]
ReqStrLong = Annotated[
    str,
    mapped_column(
        String(VERY_LONG_MAX_LEN),
        nullable=False,
    ),
]
OptStr = Annotated[
    str | None,
    mapped_column(
        String(SHORT_STR_LEN),
        nullable=True,
        default=None,
    ),
]
OptStrLong = Annotated[
    str | None,
    mapped_column(
        String(VERY_LONG_MAX_LEN),
        nullable=True,
        default=None,
    ),
]
OptJson = Annotated[
    JsonObject | None,
    mapped_column(
        JSONColumn,
        nullable=True,
        default=None,
    ),
]


def _mk_msg_metadata() -> JsonObject:
    return {}


ArbitraryMetadata = Annotated[
    JsonObject,
    mapped_column(
        JSONColumn,
        nullable=False,
        default=_mk_msg_metadata,
    ),
]


class MetadataMixin:
    """Mixin to embed common descriptive columns within an Entity."""

    title: Mapped[str | None] = mapped_column(
        String(TITLE_MAX_LEN),
        nullable=True,
        default=None,
    )
    """Relatively short primer on entity."""

    description: Mapped[str | None] = mapped_column(
        String(DESCRIPTION_MAX_LEN),
        nullable=True,
        default=None,
    )
    """Description on entity."""

    extra_detail: Mapped[str | None] = mapped_column(
        String(EXTRA_DETAIL_MAX_LEN),
        nullable=True,
        default=None,
    )
    """Larger detailment into entity."""

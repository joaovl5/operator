from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

TITLE_MAX_LEN = 200
DESCRIPTION_MAX_LEN = 1_000
EXTRA_DETAIL_MAX_LEN = 20_000


class MetadataMixin:
    title: Mapped[str] = mapped_column(
        String(TITLE_MAX_LEN),
        nullable=False,
    )
    description: Mapped[str | None] = mapped_column(
        String(DESCRIPTION_MAX_LEN),
        nullable=True,
        default=None,
    )
    extra_detail: Mapped[str | None] = mapped_column(
        String(EXTRA_DETAIL_MAX_LEN),
        nullable=True,
        default=None,
    )

"""${message}.

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}

"""

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op

if TYPE_CHECKING:
    from alembic_scripts.types import AlembicRev

# revision identifiers, used by Alembic.
revision: AlembicRev = ""
down_revision: AlembicRev = ""
branch_labels: AlembicRev = ""
depends_on: AlembicRev = ""


def upgrade() -> None:
    """Upgrade schema."""


def downgrade() -> None:
    """Downgrade schema."""

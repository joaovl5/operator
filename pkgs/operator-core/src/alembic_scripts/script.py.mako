"""${message}.

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}

"""
from typing import TYPE_CHECKING

from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

if TYPE_CHECKING:
    from alembic_scripts.types import AlembicRev

# revision identifiers, used by Alembic.
revision: AlembicRev = ${repr(up_revision)}
down_revision: AlembicRev = ${repr(down_revision)}
branch_labels: AlembicRev = ${repr(branch_labels)}
depends_on: AlembicRev = ${repr(depends_on)}


def upgrade() -> None:
    """Upgrade schema."""
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    """Downgrade schema."""
    ${downgrades if downgrades else "pass"}


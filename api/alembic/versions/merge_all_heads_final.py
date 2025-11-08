"""Merge all heads final

Revision ID: merge_all_heads_final
Revises: ('add_users_and_plans', 'merge_branches_001')
Create Date: 2025-01-11 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'merge_all_heads_final'
down_revision: Union[str, Sequence[str], None] = ('add_users_and_plans', 'merge_branches_001')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Merge all heads - no schema changes needed."""
    # This is a merge migration, so no actual schema changes
    # All branches are already applied, we're just merging the history
    pass


def downgrade() -> None:
    """Downgrade merge - no schema changes needed."""
    # This is a merge migration, so no actual schema changes
    pass


"""Merge migration branches

Revision ID: merge_branches_001
Revises: ('add_creator_vectors_table', 'smart_planner_001')
Create Date: 2025-01-11 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'merge_branches_001'
down_revision: Union[str, Sequence[str], None] = ('add_creator_vectors_table', 'smart_planner_001')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Merge branches - no schema changes needed."""
    # This is a merge migration, so no actual schema changes
    # Both branches are already applied, we're just merging the history
    pass


def downgrade() -> None:
    """Downgrade merge - no schema changes needed."""
    # This is a merge migration, so no actual schema changes
    pass


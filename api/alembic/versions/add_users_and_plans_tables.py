"""Add users and plans tables

Revision ID: add_users_and_plans
Revises: merge_branches_001
Create Date: 2025-01-11 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'add_users_and_plans'
# Depend on common ancestor - this will create a new head, but ensures the migration runs
# We can merge heads later if needed
down_revision: Union[str, Sequence[str], None] = '2a7359f2c90f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create users and plans tables."""
    
    # Create users table
    op.create_table('users',
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('password_hash', sa.String(length=255), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('user_id'),
        sa.UniqueConstraint('email')
    )
    op.create_index(op.f('ix_users_user_id'), 'users', ['user_id'], unique=False)
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)
    
    # Create plans table
    op.create_table('plans',
        sa.Column('plan_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('plan_data', postgresql.JSONB(), nullable=False),
        sa.Column('plan_request', postgresql.JSONB(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='draft'),
        sa.Column('confirmed_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['user_id'], ['users.user_id'], ),
        sa.PrimaryKeyConstraint('plan_id'),
        sa.CheckConstraint("status IN ('draft', 'confirmed', 'cancelled')", name='check_plan_status')
    )
    op.create_index(op.f('ix_plans_plan_id'), 'plans', ['plan_id'], unique=False)
    op.create_index(op.f('ix_plans_user_id'), 'plans', ['user_id'], unique=False)
    op.create_index(op.f('ix_plans_status'), 'plans', ['status'], unique=False)


def downgrade() -> None:
    """Drop users and plans tables."""
    op.drop_index(op.f('ix_plans_status'), table_name='plans')
    op.drop_index(op.f('ix_plans_user_id'), table_name='plans')
    op.drop_index(op.f('ix_plans_plan_id'), table_name='plans')
    op.drop_table('plans')
    op.drop_index(op.f('ix_users_email'), table_name='users')
    op.drop_index(op.f('ix_users_user_id'), table_name='users')
    op.drop_table('users')


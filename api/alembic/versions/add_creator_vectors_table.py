"""add_creator_vectors_table

Revision ID: add_creator_vectors_table
Revises: 2a7359f2c90f
Create Date: 2024-01-15 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_creator_vectors_table'
down_revision = '2a7359f2c90f'
branch_labels = None
depends_on = None


def upgrade():
    # Create creator_vectors table
    op.create_table('creator_vectors',
        sa.Column('creator_id', sa.Integer(), nullable=False),
        sa.Column('vector', postgresql.ARRAY(sa.Numeric()), nullable=False),
        sa.Column('vector_dimension', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['creator_id'], ['creators.creator_id'], ),
        sa.PrimaryKeyConstraint('creator_id'),
        sa.CheckConstraint('vector_dimension > 0', name='check_vector_dimension_positive')
    )


def downgrade():
    # Drop creator_vectors table
    op.drop_table('creator_vectors')

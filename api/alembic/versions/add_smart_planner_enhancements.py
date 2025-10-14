"""Add smart planner enhancements - topics, keywords, demographics, similarities

Revision ID: smart_planner_001
Revises: 2a7359f2c90f
Create Date: 2025-01-10 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'smart_planner_001'
down_revision: Union[str, Sequence[str], None] = '2a7359f2c90f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    
    # Add demographic fields to creators table
    op.add_column('creators', sa.Column('age_range', sa.String(length=10), nullable=True))
    op.add_column('creators', sa.Column('gender_skew', sa.String(length=20), nullable=True))
    op.add_column('creators', sa.Column('location', sa.String(length=10), nullable=True))
    op.add_column('creators', sa.Column('interests', sa.Text(), nullable=True))
    
    # Add target demographic fields to advertisers table
    op.add_column('advertisers', sa.Column('target_age_range', sa.String(length=10), nullable=True))
    op.add_column('advertisers', sa.Column('target_gender_skew', sa.String(length=20), nullable=True))
    op.add_column('advertisers', sa.Column('target_location', sa.String(length=10), nullable=True))
    op.add_column('advertisers', sa.Column('target_interests', sa.Text(), nullable=True))
    
    # Create topics table
    op.create_table('topics',
        sa.Column('topic_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('topic_id'),
        sa.UniqueConstraint('name')
    )
    op.create_index(op.f('ix_topics_topic_id'), 'topics', ['topic_id'], unique=False)
    op.create_index(op.f('ix_topics_name'), 'topics', ['name'], unique=False)
    
    # Create keywords table
    op.create_table('keywords',
        sa.Column('keyword_id', sa.Integer(), nullable=False),
        sa.Column('keywords', sa.Text(), nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('keyword_id')
    )
    op.create_index(op.f('ix_keywords_keyword_id'), 'keywords', ['keyword_id'], unique=False)
    
    # Create creator_topics table
    op.create_table('creator_topics',
        sa.Column('creator_id', sa.Integer(), nullable=False),
        sa.Column('topic_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['creator_id'], ['creators.creator_id'], ),
        sa.ForeignKeyConstraint(['topic_id'], ['topics.topic_id'], ),
        sa.PrimaryKeyConstraint('creator_id', 'topic_id')
    )
    
    # Create creator_keywords table
    op.create_table('creator_keywords',
        sa.Column('creator_id', sa.Integer(), nullable=False),
        sa.Column('keyword_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['creator_id'], ['creators.creator_id'], ),
        sa.ForeignKeyConstraint(['keyword_id'], ['keywords.keyword_id'], ),
        sa.PrimaryKeyConstraint('creator_id', 'keyword_id')
    )
    
    # Create creator_similarities table
    op.create_table('creator_similarities',
        sa.Column('creator_a_id', sa.Integer(), nullable=False),
        sa.Column('creator_b_id', sa.Integer(), nullable=False),
        sa.Column('similarity_type', sa.String(length=20), nullable=False),
        sa.Column('similarity_score', sa.Numeric(precision=5, scale=4), nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['creator_a_id'], ['creators.creator_id'], ),
        sa.ForeignKeyConstraint(['creator_b_id'], ['creators.creator_id'], ),
        sa.PrimaryKeyConstraint('creator_a_id', 'creator_b_id', 'similarity_type'),
        sa.CheckConstraint('creator_a_id != creator_b_id', name='check_different_creators'),
        sa.CheckConstraint('similarity_score >= 0 AND similarity_score <= 1', name='check_similarity_range')
    )


def downgrade() -> None:
    """Downgrade schema."""
    
    # Drop new tables
    op.drop_table('creator_similarities')
    op.drop_table('creator_keywords')
    op.drop_table('creator_topics')
    op.drop_table('keywords')
    op.drop_table('topics')
    
    # Remove demographic fields from advertisers table
    op.drop_column('advertisers', 'target_interests')
    op.drop_column('advertisers', 'target_location')
    op.drop_column('advertisers', 'target_gender_skew')
    op.drop_column('advertisers', 'target_age_range')
    
    # Remove demographic fields from creators table
    op.drop_column('creators', 'interests')
    op.drop_column('creators', 'location')
    op.drop_column('creators', 'gender_skew')
    op.drop_column('creators', 'age_range')

"""Create initial tables

Revision ID: b89794560fae
Revises: 
Create Date: 2025-09-30 17:06:14.449660

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'b89794560fae'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create advertisers table
    op.create_table('advertisers',
        sa.Column('advertiser_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('category', sa.String(length=100), nullable=True),
        sa.PrimaryKeyConstraint('advertiser_id')
    )
    op.create_index(op.f('ix_advertisers_advertiser_id'), 'advertisers', ['advertiser_id'], unique=False)
    op.create_index(op.f('ix_advertisers_name'), 'advertisers', ['name'], unique=True)

    # Create campaigns table
    op.create_table('campaigns',
        sa.Column('campaign_id', sa.Integer(), nullable=False),
        sa.Column('advertiser_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('end_date', sa.Date(), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['advertiser_id'], ['advertisers.advertiser_id'], ),
        sa.PrimaryKeyConstraint('campaign_id')
    )
    op.create_index(op.f('ix_campaigns_campaign_id'), 'campaigns', ['campaign_id'], unique=False)

    # Create insertions table
    op.create_table('insertions',
        sa.Column('insertion_id', sa.Integer(), nullable=False),
        sa.Column('campaign_id', sa.Integer(), nullable=False),
        sa.Column('month_start', sa.Date(), nullable=False),
        sa.Column('month_end', sa.Date(), nullable=False),
        sa.Column('cpc', sa.Numeric(precision=10, scale=4), nullable=False),
        sa.ForeignKeyConstraint(['campaign_id'], ['campaigns.campaign_id'], ),
        sa.PrimaryKeyConstraint('insertion_id')
    )
    op.create_index(op.f('ix_insertions_insertion_id'), 'insertions', ['insertion_id'], unique=False)

    # Create creators table
    op.create_table('creators',
        sa.Column('creator_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('acct_id', sa.String(length=100), nullable=False),
        sa.Column('owner_email', postgresql.CITEXT(), nullable=False),
        sa.Column('topic', sa.Text(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('creator_id')
    )
    op.create_index(op.f('ix_creators_acct_id'), 'creators', ['acct_id'], unique=True)
    op.create_index(op.f('ix_creators_creator_id'), 'creators', ['creator_id'], unique=False)
    op.create_index(op.f('ix_creators_owner_email'), 'creators', ['owner_email'], unique=True)

    # Create placements table
    op.create_table('placements',
        sa.Column('placement_id', sa.Integer(), nullable=False),
        sa.Column('insertion_id', sa.Integer(), nullable=False),
        sa.Column('creator_id', sa.Integer(), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['creator_id'], ['creators.creator_id'], ),
        sa.ForeignKeyConstraint(['insertion_id'], ['insertions.insertion_id'], ),
        sa.PrimaryKeyConstraint('placement_id')
    )
    op.create_index(op.f('ix_placements_placement_id'), 'placements', ['placement_id'], unique=False)

    # Create perf_uploads table
    op.create_table('perf_uploads',
        sa.Column('perf_upload_id', sa.Integer(), nullable=False),
        sa.Column('insertion_id', sa.Integer(), nullable=False),
        sa.Column('uploaded_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('filename', sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(['insertion_id'], ['insertions.insertion_id'], ),
        sa.PrimaryKeyConstraint('perf_upload_id')
    )
    op.create_index(op.f('ix_perf_uploads_perf_upload_id'), 'perf_uploads', ['perf_upload_id'], unique=False)

    # Create click_uniques table
    op.create_table('click_uniques',
        sa.Column('click_id', sa.Integer(), nullable=False),
        sa.Column('perf_upload_id', sa.Integer(), nullable=False),
        sa.Column('creator_id', sa.Integer(), nullable=False),
        sa.Column('execution_date', sa.Date(), nullable=False),
        sa.Column('unique_clicks', sa.Integer(), nullable=False),
        sa.Column('raw_clicks', sa.Integer(), nullable=True),
        sa.Column('flagged', sa.Boolean(), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=True),
        sa.ForeignKeyConstraint(['creator_id'], ['creators.creator_id'], ),
        sa.ForeignKeyConstraint(['perf_upload_id'], ['perf_uploads.perf_upload_id'], ),
        sa.PrimaryKeyConstraint('click_id')
    )
    op.create_index(op.f('ix_click_uniques_click_id'), 'click_uniques', ['click_id'], unique=False)

    # Create conv_uploads table
    op.create_table('conv_uploads',
        sa.Column('conv_upload_id', sa.Integer(), nullable=False),
        sa.Column('advertiser_id', sa.Integer(), nullable=False),
        sa.Column('campaign_id', sa.Integer(), nullable=False),
        sa.Column('insertion_id', sa.Integer(), nullable=False),
        sa.Column('uploaded_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('filename', sa.Text(), nullable=False),
        sa.Column('range_start', sa.Date(), nullable=False),
        sa.Column('range_end', sa.Date(), nullable=False),
        sa.Column('tz', sa.String(length=50), server_default=sa.text("'America/New_York'"), nullable=False),
        sa.ForeignKeyConstraint(['advertiser_id'], ['advertisers.advertiser_id'], ),
        sa.ForeignKeyConstraint(['campaign_id'], ['campaigns.campaign_id'], ),
        sa.ForeignKeyConstraint(['insertion_id'], ['insertions.insertion_id'], ),
        sa.PrimaryKeyConstraint('conv_upload_id')
    )
    op.create_index(op.f('ix_conv_uploads_conv_upload_id'), 'conv_uploads', ['conv_upload_id'], unique=False)

    # Create conversions table
    op.create_table('conversions',
        sa.Column('conversion_id', sa.Integer(), nullable=False),
        sa.Column('conv_upload_id', sa.Integer(), nullable=False),
        sa.Column('insertion_id', sa.Integer(), nullable=False),
        sa.Column('creator_id', sa.Integer(), nullable=False),
        sa.Column('period', postgresql.DATERANGE(), nullable=False),
        sa.Column('conversions', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['conv_upload_id'], ['conv_uploads.conv_upload_id'], ),
        sa.ForeignKeyConstraint(['creator_id'], ['creators.creator_id'], ),
        sa.ForeignKeyConstraint(['insertion_id'], ['insertions.insertion_id'], ),
        sa.PrimaryKeyConstraint('conversion_id')
    )
    op.create_index(op.f('ix_conversions_conversion_id'), 'conversions', ['conversion_id'], unique=False)

    # Create GiST exclusion constraint for conversions table
    op.create_exclude_constraint(
        'conversions_creator_id_insertion_id_period_excl',
        'conversions',
        ('creator_id', '='),
        ('insertion_id', '='),
        ('period', '&&'),
        using='gist'
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Drop tables in reverse order
    op.drop_table('conversions')
    op.drop_table('conv_uploads')
    op.drop_table('click_uniques')
    op.drop_table('perf_uploads')
    op.drop_table('placements')
    op.drop_table('creators')
    op.drop_table('insertions')
    op.drop_table('campaigns')
    op.drop_table('advertisers')

"""Add team scores to Match model

Revision ID: xxxxxxxxxxxx
Revises: previous_revision_id
Create Date: 2023-05-04 12:34:56.789012

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'xxxxxxxxxxxx'
down_revision = 'previous_revision_id'
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('matches', sa.Column('team1_score', sa.Integer(), nullable=True))
    op.add_column('matches', sa.Column('team2_score', sa.Integer(), nullable=True))

def downgrade():
    op.drop_column('matches', 'team2_score')
    op.drop_column('matches', 'team1_score')
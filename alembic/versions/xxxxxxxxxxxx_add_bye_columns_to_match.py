"""add bye columns to match

Revision ID: xxxxxxxxxxxx
Revises: f94904a9a3d9  # Updated with your current revision ID
Create Date: YYYY-MM-DD HH:MM:SS

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'xxxxxxxxxxxx'  # This will be auto-generated
down_revision = 'f94904a9a3d9'  # Updated with your current revision ID
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('matches', sa.Column('is_bye', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('matches', sa.Column('bye_description', sa.String(), nullable=True))

def downgrade():
    op.drop_column('matches', 'bye_description')
    op.drop_column('matches', 'is_bye')

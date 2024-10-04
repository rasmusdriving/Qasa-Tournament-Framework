"""add position to matches

Revision ID: <generate_a_unique_id>
Revises: <previous_revision_id>
Create Date: <current_date_and_time>

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '<generate_a_unique_id>'
down_revision = '<previous_revision_id>'
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('matches', sa.Column('position', sa.Integer(), nullable=True))

def downgrade():
    op.drop_column('matches', 'position')
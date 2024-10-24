"""fresh_start

Revision ID: f55676af8762
Revises: 
Create Date: 2024-10-24 09:23:22.975495

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f55676af8762'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('bets', sa.Column('email', sa.String(), nullable=True))
    op.drop_index('ix_bets_name', table_name='bets')
    op.drop_column('bets', 'status')
    op.alter_column('matches', 'is_bye',
               existing_type=sa.BOOLEAN(),
               server_default=None,
               nullable=True)
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('matches', 'is_bye',
               existing_type=sa.BOOLEAN(),
               server_default=sa.text('false'),
               nullable=False)
    op.add_column('bets', sa.Column('status', sa.VARCHAR(), autoincrement=False, nullable=True))
    op.create_index('ix_bets_name', 'bets', ['name'], unique=False)
    op.drop_column('bets', 'email')
    # ### end Alembic commands ###

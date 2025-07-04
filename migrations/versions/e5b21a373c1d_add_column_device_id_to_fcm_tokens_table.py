"""add column device_id to fcm_tokens table

Revision ID: e5b21a373c1d
Revises: e464b6fe3402
Create Date: 2025-06-09 14:41:43.997834

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e5b21a373c1d'
down_revision: Union[str, None] = 'e464b6fe3402'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('fcm_tokens', sa.Column('device_id', sa.String(length=64), nullable=False))
    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('fcm_tokens', 'device_id')
    # ### end Alembic commands ###

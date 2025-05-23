"""add field sha256_hash to apk_update model

Revision ID: 010bd765a207
Revises: 
Create Date: 2025-04-26 16:55:10.186283

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '010bd765a207'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('apk_updates', sa.Column('sha256_hash', sa.String(length=64), nullable=False))
    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('apk_updates', 'sha256_hash')
    # ### end Alembic commands ###

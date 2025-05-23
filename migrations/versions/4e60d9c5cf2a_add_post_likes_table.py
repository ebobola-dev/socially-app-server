"""add post_likes table

Revision ID: 4e60d9c5cf2a
Revises: c411f44bf7d2
Create Date: 2025-05-03 16:32:30.348620

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4e60d9c5cf2a'
down_revision: Union[str, None] = 'c411f44bf7d2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('post_likes',
    sa.Column('user_id', sa.CHAR(length=36), nullable=False),
    sa.Column('post_id', sa.CHAR(length=36), nullable=False),
    sa.ForeignKeyConstraint(['post_id'], ['posts.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('user_id', 'post_id')
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('post_likes')
    # ### end Alembic commands ###

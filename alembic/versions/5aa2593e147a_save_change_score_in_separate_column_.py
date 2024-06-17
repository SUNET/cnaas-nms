"""save change_score in separate column instead of putting it amongst devices in result to make things cleaner

Revision ID: 5aa2593e147a
Revises: 65b83c197420
Create Date: 2019-12-05 13:10:39.311902

"""
import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "5aa2593e147a"
down_revision = "65b83c197420"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("job", sa.Column("change_score", sa.SmallInteger(), nullable=True))


def downgrade():
    op.drop_column("job", "change_score")

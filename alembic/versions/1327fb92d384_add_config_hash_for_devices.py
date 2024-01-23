"""add config hash for devices

Revision ID: 1327fb92d384
Revises: d3aa4454ba7b
Create Date: 2019-05-23 08:40:31.711177

"""
import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "1327fb92d384"
down_revision = "d3aa4454ba7b"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("device", sa.Column("confhash", sa.String(length=64), nullable=True))


def downgrade():
    op.drop_column("device", "confhash")

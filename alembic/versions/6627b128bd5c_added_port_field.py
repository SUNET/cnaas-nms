"""Added port field

Revision ID: 6627b128bd5c
Revises: 6c6bec879fa8
Create Date: 2019-08-29 14:36:32.125191

"""
import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "6627b128bd5c"
down_revision = "6c6bec879fa8"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("device", sa.Column("port", sa.Integer()))


def downgrade():
    op.drop_column("device", "port")

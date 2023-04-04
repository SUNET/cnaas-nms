"""Add ipv6_gw field to Mgmtdomain

Revision ID: 2f9faee221a7
Revises: b7629362583c
Create Date: 2022-10-26 13:52:12.466111

"""
import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "2f9faee221a7"
down_revision = "b7629362583c"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("mgmtdomain", sa.Column("ipv6_gw", sa.Unicode(43)))


def downgrade():
    op.drop_column("mgmtdomain", "ipv6_gw")

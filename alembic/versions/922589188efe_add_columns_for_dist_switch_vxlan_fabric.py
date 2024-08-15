"""Add columns for dist switch/vxlan fabric

Revision ID: 922589188efe
Revises: 1327fb92d384
Create Date: 2019-07-30 08:42:18.956704

"""
import sqlalchemy as sa
import sqlalchemy_utils

from alembic import op

# revision identifiers, used by Alembic.
revision = "922589188efe"
down_revision = "1327fb92d384"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "device", sa.Column("infra_ip", sqlalchemy_utils.types.ip_address.IPAddressType(length=50), nullable=True)
    )
    op.add_column(
        "device", sa.Column("oob_ip", sqlalchemy_utils.types.ip_address.IPAddressType(length=50), nullable=True)
    )
    op.add_column("mgmtdomain", sa.Column("esi_mac", sa.String(length=12), nullable=True))


def downgrade():
    op.drop_column("mgmtdomain", "esi_mac")
    op.drop_column("device", "oob_ip")
    op.drop_column("device", "infra_ip")

""""Add secondary_management_ip to Device

Revision ID: adcce7d9baaa
Revises: 2f9faee221a7
Create Date: 2023-01-11 15:18:12.188994

"""
import sqlalchemy as sa
import sqlalchemy_utils

from alembic import op

# revision identifiers, used by Alembic.
revision = "adcce7d9baaa"
down_revision = "2f9faee221a7"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "device",
        sa.Column("secondary_management_ip", sqlalchemy_utils.types.ip_address.IPAddressType(length=50), nullable=True),
    )


def downgrade():
    op.drop_column("device", "secondary_management_ip")

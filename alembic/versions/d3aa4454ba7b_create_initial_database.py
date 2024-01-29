"""create initial database

Revision ID: d3aa4454ba7b
Revises: a3f3bc390462
Create Date: 2024-01-22 13:00:27.673060

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'd3aa4454ba7b'
down_revision = 'a3f3bc390462'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "site",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False, primary_key=True),
        sa.Column("description", sa.String(length=255)),
    )

    op.create_table(
        "device",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False, primary_key=True),
        sa.Column("hostname", sa.String(length=64), nullable=False),
        sa.Column("site_id", sa.Integer()),
        sa.Column("description", sa.String(length=255)),
        sa.Column("management_ip", sa.String(length=50)),
        sa.Column("dhcp_ip", sa.String(length=50)),
        sa.Column("serial", sa.String(length=64)),
        sa.Column("ztp_mac", sa.String(length=12)),
        sa.Column("platform", sa.String(length=64)),
        sa.Column("vendor", sa.String(length=64)),
        sa.Column("model", sa.String(length=64)),
        sa.Column("os_version", sa.String(length=64)),
        sa.Column("synchronized", sa.Boolean()),      
        sa.Column(
            "state",
            sa.Enum("UNKNOWN", "PRE_CONFIGURED", "DHCP_BOOT", "DISCOVERED", "INIT", "MANAGED", "MANAGED_NOIF", "UNMANAGED", name="devicestate"),
            nullable=False,
        ),
        sa.Column(
            "device_type",
            sa.Enum("UNKNOWN", "ACCESS", "DIST", "CORE", name="devicetype"),
            nullable=False,
        ),
        sa.Column("last_seen", sa.TIMESTAMP()),
        sa.UniqueConstraint("hostname"),
        sa.ForeignKeyConstraint(["site_id"], ["site.id"])
    )      

    op.create_table(
        "interface",
        sa.Column("device_id", sa.Integer(), nullable=False, primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False, primary_key=True),
        sa.Column(
            "configtype",
            sa.Enum("UNKNOWN", "UNMANAGED", "CONFIGFILE", "CUSTOM", "ACCESS_AUTO", "ACCESS_UNTAGGED", "ACCESS_TAGGED", "ACCESS_UPLINK", name="interfaceconfigtype"),
            nullable=False,
        ),
        sa.Column("data", postgresql.JSONB(astext_type=sa.Text())),
        sa.ForeignKeyConstraint(["device_id"], ["device.id"]),
    )

    op.create_table(
        "mgmtdomain",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False, primary_key=True),
        sa.Column("ipv4_gw", sa.String(length=18)),
        sa.Column("device_a_id", sa.Integer()),
        sa.Column("device_a_ip", sa.String(length=50)),
        sa.Column("device_b_id", sa.Integer()),
        sa.Column("device_b_ip", sa.String(length=50)),
        sa.Column("site_id", sa.Integer()),
        sa.Column("vlan", sa.Integer()),
        sa.Column("description", sa.String(length=255)),
        sa.ForeignKeyConstraint(["device_a_id"], ["device.id"]),
        sa.ForeignKeyConstraint(["device_b_id"], ["device.id"]),
        sa.ForeignKeyConstraint(["site_id"], ["site.id"])

    )
    
    op.create_table(
        "linknet",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False, primary_key=True),
        sa.Column("ipv4_network", sa.String(length=18)),
        sa.Column("device_a_id", sa.Integer()),
        sa.Column("device_a_ip", sa.String(length=50)),
        sa.Column("device_a_port", sa.String(length=64)),
        sa.Column("device_b_id", sa.Integer()),
        sa.Column("device_b_ip", sa.String(length=50)),
        sa.Column("device_b_port", sa.String(length=64)),
        sa.Column("site_id", sa.Integer()),
        sa.Column("description", sa.String(length=255)),
        sa.UniqueConstraint("device_a_id", "device_a_ip", name="device_a_uq"),
        sa.UniqueConstraint("device_b_id", "device_b_ip", name="device_b_uq"),
        sa.ForeignKeyConstraint(["device_a_id"], ["device.id"]),
        sa.ForeignKeyConstraint(["device_b_id"], ["device.id"]),
        sa.ForeignKeyConstraint(["site_id"], ["site.id"]),
    )


def downgrade():
    op.drop_table("linknet")
    op.drop_table("mgmtdomain")
    op.drop_table("interface")
    op.drop_table("device")
    op.drop_table("site")

    sa.Enum(name="devicetype").drop(op.get_bind(), checkfirst=False)
    sa.Enum(name="devicestate").drop(op.get_bind(), checkfirst=False)
    sa.Enum(name="interfaceconfigtype").drop(op.get_bind(), checkfirst=False)
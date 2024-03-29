"""add combined index on reservedip

Revision ID: d93fd9fa6c88
Revises: adcce7d9baaa
Create Date: 2024-03-01 15:06:45.156184

"""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision = "d93fd9fa6c88"
down_revision = "adcce7d9baaa"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(op.f("ix_reservedip_device_id"), table_name="reservedip")
    op.drop_constraint("reservedip_device_id_fkey", "reservedip", type_="foreignkey")
    op.drop_constraint("reservedip_pkey", "reservedip", type_="primary")
    op.add_column("reservedip", sa.Column("ip_version", sa.Integer(), nullable=False))
    op.create_primary_key("reservedip_pkey", "reservedip", ["device_id", "ip_version"])
    op.create_foreign_key("reservedip_device_id_fkey", "reservedip", "device", ["device_id"], ["id"])
    op.alter_column("reservedip", "ip", existing_type=sa.VARCHAR(length=50), nullable=False)
    op.alter_column("reservedip", "last_seen", existing_type=postgresql.TIMESTAMP(), nullable=False)
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint("reservedip_device_id_fkey", "reservedip")
    op.drop_constraint("reservedip_pkey", "reservedip", type_="primary")
    op.drop_column("reservedip", "ip_version")
    op.create_primary_key("reservedip_pkey", "reservedip", ["device_id"])
    op.create_index(op.f("ix_reservedip_device_id"), "reservedip", ["device_id"], unique=False)
    op.create_foreign_key("reservedip_device_id_fkey", "reservedip", "device", ["device_id"], ["id"])
    op.alter_column("reservedip", "last_seen", existing_type=postgresql.TIMESTAMP(), nullable=True)
    op.alter_column("reservedip", "ip", existing_type=sa.VARCHAR(length=50), nullable=True)
    # ### end Alembic commands ###

"""Add table for stack members

Revision ID: b7629362583c
Revises: 9d01bce3c835
Create Date: 2021-09-17 12:42:45.417807

"""
import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "b7629362583c"
down_revision = "9d01bce3c835"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "stackmember",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("device_id", sa.Integer(), nullable=False),
        sa.Column("hardware_id", sa.String(length=64), nullable=False),
        sa.Column("member_no", sa.Integer(), nullable=True),
        sa.Column("priority", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(
            ["device_id"],
            ["device.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("device_id", "member_no"),
        sa.UniqueConstraint("device_id", "hardware_id"),
    )


def downgrade():
    op.drop_table("stackmember")

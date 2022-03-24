"""add joblock database.

Revision ID: 6c6bec879fa8
Revises: 922589188efe
Create Date: 2019-08-23 10:00:17.495934

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "6c6bec879fa8"
down_revision = "922589188efe"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
        "joblock",
        sa.Column("jobid", sa.String(length=24), nullable=False),
        sa.Column("name", sa.String(length=32), nullable=False),
        sa.Column("start_time", sa.DateTime(), nullable=True),
        sa.Column("abort", sa.Boolean(), nullable=True),
        sa.PrimaryKeyConstraint("jobid"),
        sa.UniqueConstraint("jobid"),
        sa.UniqueConstraint("name"),
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table("joblock")
    # ### end Alembic commands ###

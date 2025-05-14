"""add FIREWALL devicetype

Revision ID: 3dcd43eda3de
Revises: d93fd9fa6c88
Create Date: 2025-05-14 09:17:26.256569

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '3dcd43eda3de'
down_revision = 'd93fd9fa6c88'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("COMMIT")
    op.execute("ALTER TYPE devicetype ADD VALUE 'FIREWALL' AFTER 'CORE'")


def downgrade():
    pass

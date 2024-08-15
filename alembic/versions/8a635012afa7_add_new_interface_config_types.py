"""add new interface config types

Revision ID: 8a635012afa7
Revises: 395427a732d6
Create Date: 2020-03-26 09:21:15.439761

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "8a635012afa7"
down_revision = "395427a732d6"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("COMMIT")
    op.execute("ALTER TYPE interfaceconfigtype ADD VALUE 'TEMPLATE' AFTER 'CUSTOM'")
    op.execute("ALTER TYPE interfaceconfigtype ADD VALUE 'MLAG_PEER' AFTER 'TEMPLATE'")
    op.execute("ALTER TYPE interfaceconfigtype ADD VALUE 'ACCESS_DOWNLINK' AFTER 'ACCESS_UPLINK'")


def downgrade():
    # removing extra types in an enum can make fields in the database invalid
    pass

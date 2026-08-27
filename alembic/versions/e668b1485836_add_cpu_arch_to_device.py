"""add_cpu_arch_to_device

Revision ID: e668b1485836
Revises: c1e5bd25c3a1
Create Date: 2026-08-27 11:26:32.112984

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e668b1485836'
down_revision = 'c1e5bd25c3a1'
branch_labels = None
depends_on = None


def upgrade():
    cpuarchitecture = sa.Enum('X86_32', 'X86_64', 'ARM64', name='cpuarchitecture')
    cpuarchitecture.create(op.get_bind(), checkfirst=True)
    op.add_column('device', sa.Column('cpu_arch', sa.Enum('X86_32', 'X86_64', 'ARM64', name='cpuarchitecture'), nullable=True))


def downgrade():
    op.drop_column('device', 'cpu_arch')
    sa.Enum(name='cpuarchitecture').drop(op.get_bind(), checkfirst=True)

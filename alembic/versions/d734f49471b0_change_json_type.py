"""change json type

Revision ID: d734f49471b0
Revises: b7629362583c
Create Date: 2021-10-05 09:32:14.870194

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy_utils import JSONType
from sqlalchemy.dialects.postgresql.json import JSONB


# revision identifiers, used by Alembic.
revision = 'd734f49471b0'
down_revision = 'b7629362583c'
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column('interface', 'data', type_=JSONType)
    op.alter_column('job', 'result', type_=JSONType)
    op.alter_column('job', 'exception', type_=JSONType)
    op.alter_column('job', 'finished_devices', type_=JSONType)
    op.alter_column('job', 'start_arguments', type_=JSONType)


def downgrade():
    op.alter_column('interface', 'data', type_=JSONB)
    op.alter_column('job', 'result', type_=JSONB)
    op.alter_column('job', 'exception', type_=JSONB)
    op.alter_column('job', 'finished_devices', type_=JSONB)
    op.alter_column('job', 'start_arguments', type_=JSONB)

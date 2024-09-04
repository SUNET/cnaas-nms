"""add ABORTED state for jobs

Revision ID: 395427a732d6
Revises: 5aa2593e147a
Create Date: 2019-12-06 09:49:26.610811

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "395427a732d6"
down_revision = "5aa2593e147a"
branch_labels = None
depends_on = None


def upgrade():
    op.create_index(op.f("ix_job_finish_time"), "job", ["finish_time"], unique=False)
    op.create_index(op.f("ix_job_status"), "job", ["status"], unique=False)
    op.create_index(op.f("ix_job_ticket_ref"), "job", ["ticket_ref"], unique=False)
    op.execute("COMMIT")
    op.execute("ALTER TYPE jobstatus ADD VALUE 'ABORTED' AFTER 'EXCEPTION'")


def downgrade():
    op.drop_index(op.f("ix_job_ticket_ref"), table_name="job")
    op.drop_index(op.f("ix_job_status"), table_name="job")
    op.drop_index(op.f("ix_job_finish_time"), table_name="job")
    # removing extra types in an enum can make fields in the database invalid

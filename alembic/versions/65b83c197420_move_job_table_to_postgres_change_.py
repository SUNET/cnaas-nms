"""move job table to postgres, change joblock relationship

Revision ID: 65b83c197420
Revises: 9478bbaf8010
Create Date: 2019-12-02 15:53:23.937129

"""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision = "65b83c197420"
down_revision = "9478bbaf8010"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "job",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "status",
            sa.Enum("UNKNOWN", "SCHEDULED", "RUNNING", "FINISHED", "EXCEPTION", name="jobstatus"),
            nullable=True,
        ),
        sa.Column("scheduled_time", sa.DateTime(), nullable=True),
        sa.Column("start_time", sa.DateTime(), nullable=True),
        sa.Column("finish_time", sa.DateTime(), nullable=True),
        sa.Column("function_name", sa.Unicode(length=255), nullable=True),
        sa.Column("scheduled_by", sa.Unicode(length=255), nullable=True),
        sa.Column("comment", sa.Unicode(length=255), nullable=True),
        sa.Column("ticket_ref", sa.Unicode(length=32), nullable=True),
        sa.Column("next_job_id", sa.Integer(), nullable=True),
        sa.Column("result", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("exception", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("finished_devices", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.ForeignKeyConstraint(
            ["next_job_id"],
            ["job.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.add_column("joblock", sa.Column("job_id", sa.Integer(), nullable=False))
    op.drop_constraint("joblock_jobid_key", "joblock", type_="unique")
    op.create_unique_constraint("jobid_unique", "joblock", ["job_id"])
    op.create_foreign_key("fk_joblock_job", "joblock", "job", ["job_id"], ["id"])
    op.drop_column("joblock", "jobid")


def downgrade():
    op.add_column("joblock", sa.Column("jobid", sa.VARCHAR(length=24), autoincrement=False, nullable=False))
    op.drop_constraint("fk_joblock_job", "joblock", type_="foreignkey")
    op.drop_constraint("jobid_unique", "joblock", type_="unique")
    op.create_unique_constraint("joblock_jobid_key", "joblock", ["jobid"])
    op.drop_column("joblock", "job_id")
    op.drop_table("job")
    sa.Enum(name="jobstatus").drop(op.get_bind(), checkfirst=False)

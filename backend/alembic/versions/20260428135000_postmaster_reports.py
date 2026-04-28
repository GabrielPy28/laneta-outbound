"""postmaster_reports table

Revision ID: 20260428135000
Revises: 20260413120000
Create Date: 2026-04-28

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260428135000"
down_revision: Union[str, None] = "20260413120000"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "postmaster_reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "report_type",
            sa.String(length=64),
            server_default=sa.text("'domain_health_batch'"),
            nullable=False,
        ),
        sa.Column("domains_requested", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("results_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("errors_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("email_sent", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("email_to", sa.String(length=255), nullable=True),
        sa.Column("email_error", sa.Text(), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_postmaster_reports_created_at", "postmaster_reports", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_postmaster_reports_created_at", table_name="postmaster_reports")
    op.drop_table("postmaster_reports")

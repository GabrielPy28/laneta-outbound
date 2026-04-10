"""lead_statistics table

Revision ID: 20260410140000
Revises: 20260410120000
Create Date: 2026-04-10

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260410140000"
down_revision: Union[str, None] = "20260410120000"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "lead_statistics",
        sa.Column("id_lead", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("campaign_id", sa.String(length=64), nullable=True),
        sa.Column("last_sequence_step", sa.String(length=255), nullable=True),
        sa.Column("total_opens", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("total_clicks", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("total_replies", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("lead_score", sa.Integer(), nullable=True),
        sa.Column("last_event_type", sa.String(length=64), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["id_lead"], ["leads.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id_lead"),
    )
    op.create_index("ix_lead_statistics_campaign_id", "lead_statistics", ["campaign_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_lead_statistics_campaign_id", table_name="lead_statistics")
    op.drop_table("lead_statistics")

"""lead_message_history and nullable is_qualified

Revision ID: 20260410120000
Revises: 20260409120000
Create Date: 2026-04-10

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260410120000"
down_revision: Union[str, None] = "20260409120000"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "leads",
        "is_qualified",
        existing_type=sa.Boolean(),
        nullable=True,
        server_default=sa.text("false"),
    )
    op.create_table(
        "lead_message_history",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("lead_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("message_id", sa.String(length=128), nullable=False),
        sa.Column("subject", sa.String(length=512), nullable=True),
        sa.Column("direction", sa.String(length=32), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("email_body", sa.Text(), nullable=True),
        sa.Column("reply_intent", sa.String(length=32), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["lead_id"], ["leads.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("lead_id", "message_id", name="uq_lead_message_history_lead_message"),
    )
    op.create_index("ix_lead_message_history_lead_id", "lead_message_history", ["lead_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_lead_message_history_lead_id", table_name="lead_message_history")
    op.drop_table("lead_message_history")
    op.alter_column(
        "leads",
        "is_qualified",
        existing_type=sa.Boolean(),
        nullable=False,
        server_default=sa.text("false"),
    )

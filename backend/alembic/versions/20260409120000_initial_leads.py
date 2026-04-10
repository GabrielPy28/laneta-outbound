"""initial leads table

Revision ID: 20260409120000
Revises:
Create Date: 2026-04-09

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260409120000"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "leads",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("first_name", sa.String(length=255), nullable=True),
        sa.Column("last_name", sa.String(length=255), nullable=True),
        sa.Column("company_name", sa.String(length=255), nullable=True),
        sa.Column("job_title", sa.String(length=255), nullable=True),
        sa.Column("last_email_subject", sa.String(length=512), nullable=True),
        sa.Column("company_size", sa.Integer(), nullable=True),
        sa.Column("company_category", sa.String(length=128), nullable=True),
        sa.Column("company_industry", sa.String(length=128), nullable=True),
        sa.Column("website", sa.String(length=2048), nullable=True),
        sa.Column("lead_classification", sa.String(length=32), nullable=True),
        sa.Column("country", sa.String(length=128), nullable=True),
        sa.Column("address", sa.String(length=512), nullable=True),
        sa.Column("language", sa.String(length=32), nullable=True),
        sa.Column("seniority_level", sa.String(length=64), nullable=True),
        sa.Column("engagement_status", sa.String(length=64), nullable=True),
        sa.Column("sequence_status", sa.String(length=64), nullable=True),
        sa.Column("external_lead_id", sa.String(length=128), nullable=True),
        sa.Column("hubspot_contact_id", sa.String(length=64), nullable=True),
        sa.Column("smartlead_lead_id", sa.String(length=64), nullable=True),
        sa.Column("campaign_id", sa.String(length=64), nullable=True),
        sa.Column("total_opens", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("total_clicks", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("total_replies", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("last_open_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_click_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_reply_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_contacted_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_new_lead", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("is_qualified", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("is_disqualified", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("invalid_email", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("lead_score", sa.Integer(), nullable=True),
        sa.Column("last_event_type", sa.String(length=64), nullable=True),
        sa.Column("last_event_timestamp", sa.DateTime(timezone=True), nullable=True),
        sa.Column("event_source", sa.String(length=32), nullable=True),
        sa.Column("reply_type", sa.String(length=64), nullable=True),
        sa.Column("linkedin_contacted", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("linkedin_url", sa.String(length=2048), nullable=True),
        sa.Column("last_sequence_step", sa.String(length=255), nullable=True),
        sa.Column("error_flag", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
        sa.UniqueConstraint("hubspot_contact_id"),
    )
    op.create_index("ix_leads_campaign_id", "leads", ["campaign_id"], unique=False)
    op.create_index("ix_leads_smartlead_lead_id", "leads", ["smartlead_lead_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_leads_smartlead_lead_id", table_name="leads")
    op.drop_index("ix_leads_campaign_id", table_name="leads")
    op.drop_table("leads")

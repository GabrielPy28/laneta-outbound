"""lead_deal: snapshot HubSpot deal por lead

Revision ID: 20260413120000
Revises: 20260410160000
Create Date: 2026-04-13

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260413120000"
down_revision: Union[str, None] = "20260410160000"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "lead_deal",
        sa.Column("id_lead", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("first_name", sa.String(length=255), nullable=True),
        sa.Column("email", sa.String(length=320), nullable=True),
        sa.Column("dealname", sa.String(length=512), nullable=True),
        sa.Column("dealstage_name", sa.String(length=128), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["id_lead"], ["leads.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id_lead"),
    )


def downgrade() -> None:
    op.drop_table("lead_deal")

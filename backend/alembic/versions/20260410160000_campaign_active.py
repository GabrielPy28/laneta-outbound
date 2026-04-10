"""campaign_active table for Smartlead default campaign id

Revision ID: 20260410160000
Revises: 20260410150000
Create Date: 2026-04-10

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260410160000"
down_revision: Union[str, None] = "20260410150000"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "campaign_active",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("id_campaign", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=16), server_default="Inactive", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("campaign_active")

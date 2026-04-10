"""widen lead_message_history.message_id for RFC Message-IDs

Revision ID: 20260410150000
Revises: 20260410140000
Create Date: 2026-04-10

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260410150000"
down_revision: Union[str, None] = "20260410140000"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "lead_message_history",
        "message_id",
        existing_type=sa.String(length=128),
        type_=sa.String(length=512),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "lead_message_history",
        "message_id",
        existing_type=sa.String(length=512),
        type_=sa.String(length=128),
        existing_nullable=False,
    )

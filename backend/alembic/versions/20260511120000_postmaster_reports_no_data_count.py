"""postmaster_reports: no_postmaster_data_count

Revision ID: 20260511120000
Revises: 20260428135000
Create Date: 2026-05-11

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260511120000"
down_revision: Union[str, None] = "20260428135000"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "postmaster_reports",
        sa.Column(
            "no_postmaster_data_count",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("postmaster_reports", "no_postmaster_data_count")

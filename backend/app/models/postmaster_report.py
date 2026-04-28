from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Integer, String, Text, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.db.base import Base


class PostmasterReport(Base):
    """Snapshot persistido del reporte batch de Postmaster por ejecución."""

    __tablename__ = "postmaster_reports"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    report_type: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        server_default=text("'domain_health_batch'"),
    )
    domains_requested: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    results_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    errors_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    email_sent: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    email_to: Mapped[str | None] = mapped_column(String(255), nullable=True)
    email_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class LeadStatistics(Base):
    """Métricas de engagement por lead sincronizadas desde Smartlead leads-export."""

    __tablename__ = "lead_statistics"

    id_lead: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("leads.id", ondelete="CASCADE"),
        primary_key=True,
    )
    campaign_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    last_sequence_step: Mapped[str | None] = mapped_column(String(255), nullable=True)
    total_opens: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    total_clicks: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    total_replies: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    lead_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_event_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

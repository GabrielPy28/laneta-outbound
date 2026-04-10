from __future__ import annotations

import uuid
from datetime import datetime

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Integer, String, Text, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.lead_message_history import LeadMessageHistory


class Lead(Base):
    """Lead outbound alineado a HubSpot / Smartlead y `properties.csv`."""

    __tablename__ = "leads"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)

    first_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    company_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    job_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_email_subject: Mapped[str | None] = mapped_column(String(512), nullable=True)

    company_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    company_category: Mapped[str | None] = mapped_column(String(128), nullable=True)
    company_industry: Mapped[str | None] = mapped_column(String(128), nullable=True)
    website: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    lead_classification: Mapped[str | None] = mapped_column(String(32), nullable=True)

    country: Mapped[str | None] = mapped_column(String(128), nullable=True)
    address: Mapped[str | None] = mapped_column(String(512), nullable=True)
    language: Mapped[str | None] = mapped_column(String(32), nullable=True)
    seniority_level: Mapped[str | None] = mapped_column(String(64), nullable=True)

    engagement_status: Mapped[str | None] = mapped_column(String(64), nullable=True)
    sequence_status: Mapped[str | None] = mapped_column(String(64), nullable=True)

    external_lead_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    hubspot_contact_id: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)
    smartlead_lead_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    campaign_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)

    total_opens: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    total_clicks: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    total_replies: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))

    last_open_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_click_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_reply_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_contacted_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    is_new_lead: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    is_qualified: Mapped[bool | None] = mapped_column(Boolean, nullable=True, server_default=text("false"))
    is_disqualified: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    invalid_email: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))

    lead_score: Mapped[int | None] = mapped_column(Integer, nullable=True)

    last_event_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_event_timestamp: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    event_source: Mapped[str | None] = mapped_column(String(32), nullable=True)
    reply_type: Mapped[str | None] = mapped_column(String(64), nullable=True)

    linkedin_contacted: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    linkedin_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    last_sequence_step: Mapped[str | None] = mapped_column(String(255), nullable=True)

    error_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    message_history: Mapped[list["LeadMessageHistory"]] = relationship(
        "LeadMessageHistory",
        back_populates="lead",
        cascade="all, delete-orphan",
    )

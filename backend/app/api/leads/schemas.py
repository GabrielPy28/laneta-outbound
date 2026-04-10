from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class LeadListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    first_name: str | None
    last_name: str | None
    company_name: str | None
    job_title: str | None
    engagement_status: str | None
    sequence_status: str | None
    campaign_id: str | None
    smartlead_lead_id: str | None
    hubspot_contact_id: str | None
    total_opens: int
    total_clicks: int
    total_replies: int
    last_sequence_step: str | None
    lead_score: int | None
    reply_type: str | None
    is_qualified: bool | None
    updated_at: datetime


class LeadListResponse(BaseModel):
    items: list[LeadListItem]
    total: int = Field(
        ...,
        description="Total de filas que cumplen los filtros (para paginación).",
    )


class LeadActivityHeader(BaseModel):
    """Datos mínimos para breadcrumb y cabecera."""

    id: uuid.UUID
    email: str
    first_name: str | None
    last_name: str | None
    display_name: str = Field(..., description="Nombre legible para UI.")


class LeadStatisticsActivityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    campaign_id: str | None
    last_sequence_step: str | None
    total_opens: int
    total_clicks: int
    total_replies: int
    lead_score: int | None
    last_event_type: str | None
    updated_at: datetime


class LeadMessageHistoryActivityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    message_id: str
    subject: str | None
    direction: str
    sent_at: datetime | None
    opened_at: datetime | None
    received_at: datetime | None
    email_body: str | None
    reply_intent: str | None
    created_at: datetime


class LeadActivityResponse(BaseModel):
    lead: LeadActivityHeader
    statistics: LeadStatisticsActivityOut | None
    messages: list[LeadMessageHistoryActivityOut]

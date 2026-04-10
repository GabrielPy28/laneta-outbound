from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select

from app.api.auth_deps import get_access_token_payload
from app.api.deps import DbSession
from app.api.leads.schemas import (
    LeadActivityHeader,
    LeadActivityResponse,
    LeadListItem,
    LeadListResponse,
    LeadMessageHistoryActivityOut,
    LeadStatisticsActivityOut,
)
from app.models.lead import Lead
from app.models.lead_message_history import LeadMessageHistory
from app.models.lead_statistics import LeadStatistics
from app.services.leads_query import apply_lead_filters, count_leads, lead_filter_conditions

router = APIRouter(tags=["leads"])

ALLOWED_PAGE_SIZES = frozenset({25, 50, 100})


def _lead_display_name(lead: Lead) -> str:
    parts = [p for p in [(lead.first_name or "").strip(), (lead.last_name or "").strip()] if p]
    return " ".join(parts) if parts else lead.email


def _message_sort_ts(m: LeadMessageHistory):
    return m.sent_at or m.received_at or m.created_at


@router.get(
    "/{lead_id}/activity",
    response_model=LeadActivityResponse,
    summary="Actividad del lead (KPI + historial)",
    description="Estadísticas (`lead_statistics`) e historial de mensajes (`lead_message_history`). JWT requerido.",
)
def get_lead_activity(
    lead_id: uuid.UUID,
    db: DbSession,
    _payload: dict[str, Any] = Depends(get_access_token_payload),
) -> LeadActivityResponse:
    lead = db.get(Lead, lead_id)
    if lead is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead no encontrado.")

    stats_row = db.get(LeadStatistics, lead_id)
    stats = LeadStatisticsActivityOut.model_validate(stats_row) if stats_row else None

    msg_stmt = select(LeadMessageHistory).where(LeadMessageHistory.lead_id == lead_id)
    raw_messages = list(db.scalars(msg_stmt).all())
    raw_messages.sort(key=_message_sort_ts)
    messages = [LeadMessageHistoryActivityOut.model_validate(m) for m in raw_messages]

    header = LeadActivityHeader(
        id=lead.id,
        email=lead.email,
        first_name=lead.first_name,
        last_name=lead.last_name,
        display_name=_lead_display_name(lead),
    )
    return LeadActivityResponse(lead=header, statistics=stats, messages=messages)


@router.get(
    "",
    response_model=LeadListResponse,
    summary="Listar leads",
    description=(
        "Lista paginada de `leads` con filtros opcionales (coincidencia parcial, sin distinguir "
        "mayúsculas). Requiere `Authorization: Bearer`."
    ),
)
def get_leads(
    db: DbSession,
    _payload: dict[str, Any] = Depends(get_access_token_payload),
    skip: int = Query(0, ge=0, description="Desplazamiento (offset)."),
    limit: int = Query(25, description="Tamaño de página: 25, 50 o 100."),
    filter_name: str | None = Query(None, description="Nombre o apellido (contiene)."),
    filter_email: str | None = Query(None, description="Email (contiene)."),
    filter_company: str | None = Query(None, description="Empresa (contiene)."),
    filter_engagement: str | None = Query(None, description="Engagement (contiene)."),
    filter_campaign: str | None = Query(None, description="ID campaña (contiene)."),
    filter_last_sequence: str | None = Query(
        None,
        description="Última secuencia de mensaje (contiene).",
    ),
) -> LeadListResponse:
    if limit not in ALLOWED_PAGE_SIZES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="limit debe ser 25, 50 o 100.",
        )

    conditions = lead_filter_conditions(
        filter_name=filter_name,
        filter_email=filter_email,
        filter_company=filter_company,
        filter_engagement=filter_engagement,
        filter_campaign=filter_campaign,
        filter_last_sequence=filter_last_sequence,
    )

    total = count_leads(db, conditions)

    stmt = select(Lead).order_by(Lead.updated_at.desc())
    stmt = apply_lead_filters(stmt, conditions)
    stmt = stmt.offset(skip).limit(limit)
    rows = db.scalars(stmt).all()
    items = [LeadListItem.model_validate(r) for r in rows]
    return LeadListResponse(items=items, total=total)

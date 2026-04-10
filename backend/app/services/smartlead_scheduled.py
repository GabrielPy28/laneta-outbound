"""Consultas para jobs programados (leads en secuencia activa)."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.lead import Lead


def _active_smartlead_lead_predicate():
    return (
        Lead.smartlead_lead_id.is_not(None),
        func.lower(func.coalesce(Lead.sequence_status, "")) == "active",
    )


def list_active_smartlead_lead_ids_for_campaign(session: Session, campaign_id: str) -> list[uuid.UUID]:
    """
    Leads con `sequence_status` ACTIVE (insensible a mayúsculas), misma `campaign_id`,
    y con `smartlead_lead_id` para poder llamar a message-history.
    """
    cid = str(campaign_id).strip()
    stmt = (
        select(Lead.id)
        .where(Lead.campaign_id == cid)
        .where(*_active_smartlead_lead_predicate())
    )
    return list(session.scalars(stmt).all())


def list_active_smartlead_lead_ids(session: Session) -> list[uuid.UUID]:
    """Todos los leads ACTIVE con `smartlead_lead_id` (cualquier `campaign_id` en BD)."""
    stmt = select(Lead.id).where(*_active_smartlead_lead_predicate())
    return list(session.scalars(stmt).all())


def list_distinct_campaign_ids_for_active_smartlead_leads(session: Session) -> list[str]:
    """
    `campaign_id` distintos no vacíos entre leads ACTIVE con Smartlead.
    Sirve para llamar al export CSV una vez por campaña real en BD (según `Lead.campaign_id`).
    """
    stmt = (
        select(Lead.campaign_id)
        .where(Lead.campaign_id.is_not(None))
        .where(Lead.campaign_id != "")
        .where(*_active_smartlead_lead_predicate())
        .distinct()
    )
    raw = session.scalars(stmt).all()
    return sorted({str(c).strip() for c in raw if c and str(c).strip()})

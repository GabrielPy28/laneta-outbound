"""Resolución del ID de campaña Smartlead para nuevas altas (tabla `campaign_active`)."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.integrations.smartlead.constants import SMARTLEAD_DEFAULT_CAMPAIGN_ID
from app.models.campaign_active import CampaignActive

STATUS_ACTIVE = "Active"
STATUS_INACTIVE = "Inactive"


def get_effective_smartlead_campaign_id(session: Session) -> str:
    """
    Última fila con `status` Active (insensible a mayúsculas).
    Si no hay ninguna, `SMARTLEAD_DEFAULT_CAMPAIGN_ID`.
    """
    stmt = (
        select(CampaignActive.id_campaign)
        .where(func.lower(CampaignActive.status) == func.lower(STATUS_ACTIVE))
        .order_by(CampaignActive.updated_at.desc())
        .limit(1)
    )
    raw = session.scalar(stmt)
    cid = (raw or "").strip()
    return cid or SMARTLEAD_DEFAULT_CAMPAIGN_ID


def get_active_campaign_row(session: Session) -> CampaignActive | None:
    stmt = (
        select(CampaignActive)
        .where(func.lower(CampaignActive.status) == func.lower(STATUS_ACTIVE))
        .order_by(CampaignActive.updated_at.desc())
        .limit(1)
    )
    return session.scalars(stmt).first()


def set_active_campaign(session: Session, id_campaign: str) -> CampaignActive:
    """
    Marca todas las filas como Inactive e inserta un nuevo registro Active.
    """
    cid = id_campaign.strip()
    if not cid:
        raise ValueError("id_campaign no puede estar vacío.")

    session.execute(update(CampaignActive).values(status=STATUS_INACTIVE))
    row = CampaignActive(
        id=uuid.uuid4(),
        id_campaign=cid,
        status=STATUS_ACTIVE,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return row

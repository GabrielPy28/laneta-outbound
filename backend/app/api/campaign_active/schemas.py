from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CampaignActiveRowOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    id_campaign: str
    status: str
    created_at: datetime
    updated_at: datetime


class CampaignActiveGetResponse(BaseModel):
    """Estado actual: fila activa (si existe) e ID efectivo usado por sync/push."""

    active: CampaignActiveRowOut | None
    effective_id_campaign: str = Field(
        ...,
        description="Valor que usa el backend si no envías otro en endpoints Smartlead.",
    )


class CampaignActiveSetBody(BaseModel):
    id_campaign: str = Field(..., min_length=1, max_length=64)


class CampaignActiveSetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    id_campaign: str
    status: str
    created_at: datetime
    updated_at: datetime
    effective_id_campaign: str

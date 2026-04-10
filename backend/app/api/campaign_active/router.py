from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.auth_deps import get_access_token_payload
from app.api.deps import DbSession
from app.api.campaign_active.schemas import (
    CampaignActiveGetResponse,
    CampaignActiveRowOut,
    CampaignActiveSetBody,
    CampaignActiveSetResponse,
)
from app.services import campaign_active as campaign_active_service

router = APIRouter(tags=["campaign-active"])


@router.get(
    "",
    response_model=CampaignActiveGetResponse,
    summary="Campaña activa para nuevas altas",
    description=(
        "Lee la fila `Active` más reciente en `campaign_active` y el ID efectivo "
        "(fallback al default en código si no hay ninguna)."
    ),
)
def get_campaign_active(
    db: DbSession,
    _payload: dict[str, Any] = Depends(get_access_token_payload),
) -> CampaignActiveGetResponse:
    row = campaign_active_service.get_active_campaign_row(db)
    effective = campaign_active_service.get_effective_smartlead_campaign_id(db)
    return CampaignActiveGetResponse(
        active=CampaignActiveRowOut.model_validate(row) if row else None,
        effective_id_campaign=effective,
    )


@router.put(
    "",
    response_model=CampaignActiveSetResponse,
    summary="Establecer campaña activa",
    description=(
        "Desactiva registros previos e inserta uno nuevo en estado Active. "
        "Ese `id_campaign` usará el job HubSpot→Smartlead y el push por defecto."
    ),
)
def put_campaign_active(
    db: DbSession,
    body: CampaignActiveSetBody,
    _payload: dict[str, Any] = Depends(get_access_token_payload),
) -> CampaignActiveSetResponse:
    try:
        row = campaign_active_service.set_active_campaign(db, body.id_campaign)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e

    effective = campaign_active_service.get_effective_smartlead_campaign_id(db)
    return CampaignActiveSetResponse(
        id=row.id,
        id_campaign=row.id_campaign,
        status=row.status,
        created_at=row.created_at,
        updated_at=row.updated_at,
        effective_id_campaign=effective,
    )

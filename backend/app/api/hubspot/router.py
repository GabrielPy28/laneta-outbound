from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import DbSession
from app.api.hubspot.schemas import HubSpotNewLeadsSyncResponse
from app.core.config import get_settings
from app.integrations.hubspot.client import HubSpotClient, HubSpotClientError
from app.services.hubspot_ingest import sync_new_leads_from_hubspot

router = APIRouter(tags=["hubspot"])


def get_hubspot_client() -> HubSpotClient:
    settings = get_settings()
    token = settings.hubspot_access_token
    if not token or not token.strip():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="HubSpot no configurado: falta HUBSPOT_ACCESS_TOKEN (o HUBSPOT_API_KEY).",
    )
    try:
        return HubSpotClient(access_token=token.strip())
    except HubSpotClientError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc


@router.post(
    "/sync-new-leads",
    response_model=HubSpotNewLeadsSyncResponse,
    summary="Ingestar contactos nuevos desde HubSpot",
    description=(
        "Busca contactos con `is_new_lead=true`, hace upsert en la base local "
        "y marca `is_new_lead=false` en HubSpot para evitar re-ingesta."
    ),
)
def post_sync_new_leads(
    db: DbSession,
    client: HubSpotClient = Depends(get_hubspot_client),
) -> HubSpotNewLeadsSyncResponse:
    result = sync_new_leads_from_hubspot(db, client)
    return HubSpotNewLeadsSyncResponse(
        pages_fetched=result.pages_fetched,
        contacts_scanned=result.contacts_scanned,
        created=result.created,
        updated=result.updated,
        skipped_no_email=result.skipped_no_email,
        hubspot_marked_done=result.hubspot_marked_done,
        hubspot_mark_failed=result.hubspot_mark_failed,
        errors=result.errors,
    )

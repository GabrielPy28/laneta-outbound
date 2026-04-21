from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import DbSession
from app.api.hubspot.schemas import HubSpotNewLeadsSyncResponse, ManychatHubSpotSyncResponse
from app.core.config import get_settings
from app.integrations.hubspot.client import HubSpotClient, HubSpotClientError
from app.integrations.manychat.client import ManychatClient
from app.services.hubspot_ingest import sync_new_leads_from_hubspot
from app.services.manychat_hubspot_sync import sync_manychat_contact_to_hubspot

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


def get_manychat_client() -> ManychatClient:
    settings = get_settings()
    api_key = settings.manychat_api_key
    if not api_key or not api_key.strip():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Manychat no configurado: falta MANYCHAT_API_KEY.",
        )
    return ManychatClient(api_key=api_key.strip())


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


@router.post(
    "/sync-manychat-contact/{id_contact}",
    response_model=ManychatHubSpotSyncResponse,
    summary="Sincronizar datos de conversación Manychat hacia HubSpot",
    description=(
        "Consulta el subscriber en Manychat por `id_contact`, busca el contacto en HubSpot "
        "por `firstname` con paginación, selecciona el mejor match por `lastname` y `phone`, "
        "actualiza propiedades en HubSpot y guarda `hubspot_id` en Manychat."
    ),
)
def post_sync_manychat_contact(
    id_contact: str,
    hubspot: HubSpotClient = Depends(get_hubspot_client),
    manychat: ManychatClient = Depends(get_manychat_client),
) -> ManychatHubSpotSyncResponse:
    result = sync_manychat_contact_to_hubspot(
        id_contact=id_contact,
        manychat=manychat,
        hubspot=hubspot,
    )
    return ManychatHubSpotSyncResponse(
        id_contact=result.id_contact,
        manychat_id=result.manychat_id,
        hubspot_contact_id=result.hubspot_contact_id,
        candidates_scanned=result.candidates_scanned,
        matched_by=result.matched_by,
        hubspot_updated=result.hubspot_updated,
        manychat_updated=result.manychat_updated,
        errors=result.errors,
    )

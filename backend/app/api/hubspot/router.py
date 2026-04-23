from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import DbSession
from app.api.hubspot.schemas import (
    CreateHubSpotCallRequest,
    CreateHubSpotCallResponse,
    CreateHubSpotMeetingRequest,
    CreateHubSpotMeetingResponse,
    HubSpotCallListItem,
    HubSpotMeetingListItem,
    HubSpotNewLeadsSyncResponse,
    ManychatHubSpotSyncResponse,
)
from app.core.config import get_settings
from app.integrations.google_calendar.client import GoogleCalendarError
from app.integrations.hubspot.client import HubSpotClient, HubSpotClientError
from app.integrations.manychat.client import ManychatClient
from app.services.hubspot_calls import create_call_link_contact, list_calls_with_contact_details
from app.services.hubspot_meetings import (
    create_meeting_with_calendar_and_contact,
    list_meetings_with_contact_details,
)
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


@router.get(
    "/calls",
    response_model=list[HubSpotCallListItem],
    summary="Listar llamadas asociadas a un contacto",
    description=(
        "Recorre todas las páginas (100 por página) del listado de llamadas HubSpot, "
        "filtra las que tienen `associations.contacts`, y devuelve datos de la llamada "
        "más propiedades del contacto (`firstname`, `lastname`, `call_start_time`, "
        "`call_end_time`, `estatus_llamada`)."
    ),
)
def get_hubspot_calls_with_contacts(
    hubspot: HubSpotClient = Depends(get_hubspot_client),
) -> list[HubSpotCallListItem]:
    try:
        rows = list_calls_with_contact_details(hubspot)
    except ValueError as exc:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
    except HubSpotClientError as exc:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
    return [HubSpotCallListItem.model_validate(r) for r in rows]


@router.post(
    "/meetings",
    response_model=CreateHubSpotMeetingResponse,
    summary="Crear reunión en Google Calendar + HubSpot y asociar al contacto",
    description=(
        "Crea el evento en Google Calendar (`htmlLink` → `hs_meeting_external_url`), "
        "crea la reunión CRM 2026-03, pone el deal del contacto en etapa Reunión agendada "
        "y asocia reunión↔contacto (`associations/default/contact`)."
    ),
)
def post_create_hubspot_meeting(
    body: CreateHubSpotMeetingRequest,
    hubspot: HubSpotClient = Depends(get_hubspot_client),
) -> CreateHubSpotMeetingResponse:
    settings = get_settings()
    additional_notes: str | None = body.additional_notes
    if additional_notes is not None:
        additional_notes = additional_notes.strip() or None
    try:
        out = create_meeting_with_calendar_and_contact(
            settings,
            hubspot,
            crm_contact_id=body.crm_contact_id.strip(),
            email=str(body.email),
            title=body.title.strip(),
            description=body.description.strip(),
            additional_notes=additional_notes,
            start_time=body.start_time,
            end_time=body.end_time,
        )
    except LookupError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    except GoogleCalendarError as exc:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
    except HubSpotClientError as exc:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    return CreateHubSpotMeetingResponse(
        id=out.meeting_id,
        hs_meeting_title=out.hs_meeting_title,
        hs_meeting_body=out.hs_meeting_body,
        hs_internal_meeting_notes=out.hs_internal_meeting_notes,
        hs_meeting_external_url=out.hs_meeting_external_url,
        hs_meeting_start_time=out.hs_meeting_start_time,
        hs_meeting_end_time=out.hs_meeting_end_time,
        hubspot_contact_id=out.hubspot_contact_id,
        hubspot_deal_id=out.hubspot_deal_id,
        calendar_html_link=out.calendar_html_link,
    )


@router.get(
    "/meetings",
    response_model=list[HubSpotMeetingListItem],
    summary="Listar reuniones asociadas a un contacto",
    description=(
        "Recorre páginas (100 por página) en meetings, valida `paging.next.link`, "
        "filtra reuniones con `associations.contacts` y devuelve datos de meeting + "
        "firstname/lastname + hubspot_deal_id."
    ),
)
def get_hubspot_meetings_with_contacts(
    hubspot: HubSpotClient = Depends(get_hubspot_client),
) -> list[HubSpotMeetingListItem]:
    try:
        rows = list_meetings_with_contact_details(hubspot)
    except ValueError as exc:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
    except HubSpotClientError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    return [HubSpotMeetingListItem.model_validate(r) for r in rows]


@router.post(
    "/calls",
    response_model=CreateHubSpotCallResponse,
    summary="Crear llamada HubSpot y asociarla al contacto",
    description=(
        "Crea un objeto call (CRM 2026-03), busca el contacto por la propiedad `crm_contact_id`, "
        "actualiza `call_start_time` y `call_end_time` en el contacto, y ejecuta la asociación "
        "call→contact (tipo configurable, ver HUBSPOT_CALL_CONTACT_ASSOCIATION_TYPE_ID)."
    ),
)
def post_create_hubspot_call(
    body: CreateHubSpotCallRequest,
    hubspot: HubSpotClient = Depends(get_hubspot_client),
) -> CreateHubSpotCallResponse:
    settings = get_settings()
    try:
        out = create_call_link_contact(
            hubspot,
            crm_contact_id=body.crm_contact_id.strip(),
            to_number=body.to_number.strip(),
            from_number=body.from_number.strip(),
            title=body.title.strip(),
            body=body.body.strip(),
            call_start_time=body.call_start_time,
            call_end_time=body.call_end_time,
            association_type_id=int(settings.hubspot_call_contact_association_type_id),
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except HubSpotClientError as exc:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    return CreateHubSpotCallResponse(
        id=out.call_id,
        hs_body_preview=out.hs_body_preview,
        hs_call_title=out.hs_call_title,
        hs_call_to_number=out.hs_call_to_number,
        hs_call_from_number=out.hs_call_from_number,
        hs_timestamp=out.hs_timestamp,
        hubspot_contact_id=out.hubspot_contact_id,
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

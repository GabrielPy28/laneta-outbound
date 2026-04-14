import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import DbSession, OptionalHubSpotClient
from app.api.smartlead.schemas import (
    MessageHistorySyncResponse,
    SmartleadLeadStatisticsSyncResponse,
    SmartleadPushCampaignResponse,
)
from app.core.config import get_settings
from app.integrations.smartlead.client import SmartleadClient
from app.integrations.smartlead.constants import SMARTLEAD_DEFAULT_CAMPAIGN_ID
from app.models.lead import Lead
from app.services.campaign_active import get_effective_smartlead_campaign_id
from app.services.smartlead_lead_statistics import sync_lead_statistics_from_smartlead_export
from app.services.smartlead_message_history import sync_smartlead_message_history_for_lead
from app.services.smartlead_push import push_new_leads_to_smartlead_campaign

router = APIRouter(tags=["smartlead"])


def get_smartlead_client() -> SmartleadClient:
    settings = get_settings()
    key = settings.smartlead_api_key
    if not key or not str(key).strip():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Smartlead no configurado: falta SMARTLEAD_API_KEY.",
        )
    return SmartleadClient(api_key=str(key).strip())


@router.post(
    "/push-campaign-leads",
    response_model=SmartleadPushCampaignResponse,
    summary="Enviar leads nuevos a la campaña Smartlead",
    description=(
        "Toma leads locales sin `smartlead_lead_id`, los agrega a la campaña activa en `campaign_active` "
        f"(o fallback {SMARTLEAD_DEFAULT_CAMPAIGN_ID}), resuelve el id con `GET /api/v1/leads/?email=` "
        "(sin listar la campaña) y actualiza "
        "HubSpot (`engagement_status`, `sequence_status`, `smartlead_lead_id`, `campaign_id`) "
        "cuando hay `hubspot_contact_id` y token HubSpot."
    ),
)
def post_push_campaign_leads(
    db: DbSession,
    hubspot: OptionalHubSpotClient,
    smartlead: SmartleadClient = Depends(get_smartlead_client),
    max_leads: int = Query(
        400,
        ge=1,
        le=10_000,
        description="Máximo de filas de `leads` a procesar en esta llamada (se fracciona en lotes de 400).",
    ),
) -> SmartleadPushCampaignResponse:
    result = push_new_leads_to_smartlead_campaign(
        db,
        smartlead,
        hubspot,
        campaign_id=get_effective_smartlead_campaign_id(db),
        max_leads=max_leads,
    )
    return SmartleadPushCampaignResponse(
        campaign_id=result.campaign_id,
        leads_selected=result.leads_selected,
        batches_posted=result.batches_posted,
        smartlead_added_count=result.smartlead_added_count,
        smartlead_skipped_count=result.smartlead_skipped_count,
        leads_resolved=result.leads_resolved,
        leads_unresolved=result.leads_unresolved,
        db_updated=result.db_updated,
        hubspot_patched=result.hubspot_patched,
        hubspot_failed=result.hubspot_failed,
        hubspot_skipped_no_contact=result.hubspot_skipped_no_contact,
        hubspot_available=hubspot is not None,
        errors=result.errors,
    )


@router.post(
    "/sync-campaign-lead-statistics",
    response_model=SmartleadLeadStatisticsSyncResponse,
    summary="Sincronizar estadísticas de leads desde export Smartlead",
    description=(
        "Llama a `GET .../campaigns/{campaign_id}/leads-export`, parsea el CSV con pandas, "
        "actualiza `lead_statistics` y campos equivalentes en `Lead` para leads con "
        "`campaign_id` coincidente y `smartlead_lead_id` presente en el export; "
        "parcha HubSpot (`last_sequence_step`, `total_clicks`, `total_opens`, `lead_score`, "
        "`last_event_type`, `engagement_status` por conteos, `reply_type` ← columna `category` "
        "(Interested, Meeting Request, …), `is_qualified` ← `is_interested`. "
        "Con `reply_count` y categoría positiva: `manual-complete` + `sequence_status` completed "
        "en mismo dominio; Not Interested / Follow Up Later: pause solo ese lead + paused. "
        "Tras cada PATCH de contacto exitoso: actualiza `dealstage` del deal asociado en HubSpot y `lead_deal`."
    ),
)
def post_sync_campaign_lead_statistics(
    db: DbSession,
    hubspot: OptionalHubSpotClient,
    smartlead: SmartleadClient = Depends(get_smartlead_client),
    campaign_id: str | None = Query(
        None,
        description="ID de campaña Smartlead (omitir para usar la campaña activa en BD; debe coincidir con `Lead.campaign_id`).",
    ),
) -> SmartleadLeadStatisticsSyncResponse:
    cid = (campaign_id or "").strip() or get_effective_smartlead_campaign_id(db)
    result = sync_lead_statistics_from_smartlead_export(
        db,
        smartlead,
        hubspot,
        campaign_id=cid,
    )
    return SmartleadLeadStatisticsSyncResponse(
        campaign_id=result.campaign_id,
        export_rows=result.export_rows,
        matched_leads=result.matched_leads,
        statistics_upserted=result.statistics_upserted,
        hubspot_patched=result.hubspot_patched,
        hubspot_failed=result.hubspot_failed,
        hubspot_skipped_no_contact=result.hubspot_skipped_no_contact,
        hubspot_deals_patched=result.hubspot_deals_patched,
        hubspot_deals_failed=result.hubspot_deals_failed,
        hubspot_deals_skipped_no_deal=result.hubspot_deals_skipped_no_deal,
        hubspot_available=hubspot is not None,
        errors=result.errors,
    )


@router.post(
    "/leads/{lead_id}/sync-message-history",
    response_model=MessageHistorySyncResponse,
    summary="Sincronizar historial de mensajes Smartlead",
    description=(
        "Llama a `GET .../campaigns/{campaign_id}/leads/{lead_id}/message-history` "
        "(`history[]`: SENT/REPLY, …), guarda en `lead_message_history`, "
        "actualiza `Lead` y HubSpot (`hs_email_last_open_date`, `nombre_ultimo_mensaje`, "
        "`ultima_respuesta_de_mensaje` = asunto Re: del inbound). "
        "`last_sequence_step` y `sequence_status` los actualiza `sync-campaign-lead-statistics`."
    ),
)
def post_sync_message_history(
    lead_id: uuid.UUID,
    db: DbSession,
    hubspot: OptionalHubSpotClient,
    smartlead: SmartleadClient = Depends(get_smartlead_client),
) -> MessageHistorySyncResponse:
    if db.get(Lead, lead_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead no encontrado.")
    result = sync_smartlead_message_history_for_lead(
        db,
        smartlead,
        hubspot,
        lead_id=lead_id,
    )
    return MessageHistorySyncResponse(
        lead_id=result.lead_id,
        messages_upserted=result.messages_upserted,
        has_inbound_reply=result.has_inbound_reply,
        reply_intent=result.reply_intent,
        hubspot_patched=result.hubspot_patched,
        hubspot_available=hubspot is not None,
        smartlead_paused_count=result.smartlead_paused_count,
        errors=result.errors,
    )

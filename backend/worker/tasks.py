"""Tareas Celery: HubSpot + Smartlead programados."""

from __future__ import annotations

import logging
from dataclasses import asdict

from app.core.config import get_settings
from app.db.session import create_session
from app.integrations.hubspot.client import HubSpotClient
from app.integrations.smartlead.client import SmartleadClient
from app.services.campaign_active import get_effective_smartlead_campaign_id
from app.services.hubspot_ingest import sync_new_leads_from_hubspot
from app.services.smartlead_lead_statistics import sync_lead_statistics_from_smartlead_export
from app.services.smartlead_message_history import sync_smartlead_message_history_for_lead
from app.services.smartlead_push import push_new_leads_to_smartlead_campaign
from app.services.smartlead_scheduled import (
    list_active_smartlead_lead_ids,
    list_distinct_campaign_ids_for_active_smartlead_leads,
)
from worker.celery_app import celery

logger = logging.getLogger(__name__)


def _hubspot_optional() -> HubSpotClient | None:
    token = (get_settings().hubspot_access_token or "").strip()
    if not token:
        return None
    return HubSpotClient(access_token=token)


def _smartlead_optional() -> SmartleadClient | None:
    key = (get_settings().smartlead_api_key or "").strip()
    if not key:
        return None
    return SmartleadClient(api_key=key)


@celery.task(name="hubspot.fetch_new_leads")
def fetch_new_leads_task() -> dict:
    """Solo ingesta HubSpot (compatibilidad). Preferir `hubspot_sync_and_smartlead_push`."""
    hs = _hubspot_optional()
    if hs is None:
        return {"ok": False, "error": "missing_hubspot_token"}

    db = create_session()
    try:
        result = sync_new_leads_from_hubspot(db, hs)
        return {"ok": True, **asdict(result)}
    finally:
        db.close()


@celery.task(name="worker.tasks.hubspot_sync_and_smartlead_push")
def hubspot_sync_and_smartlead_push() -> dict:
    """Sync nuevos leads desde HubSpot y push a la campaña activa (`campaign_active`)."""
    hs = _hubspot_optional()
    if hs is None:
        return {"ok": False, "error": "missing_hubspot_token"}

    sl = _smartlead_optional()
    if sl is None:
        return {"ok": False, "error": "missing_smartlead_api_key"}

    db = create_session()
    try:
        campaign_id = get_effective_smartlead_campaign_id(db)
        ingest = sync_new_leads_from_hubspot(db, hs)
        push = push_new_leads_to_smartlead_campaign(
            db,
            sl,
            hs,
            campaign_id=campaign_id,
            max_leads=400,
        )
        logger.info(
            "hubspot_sync_and_smartlead_push campaign_id=%s ingest=%s push_selected=%s",
            campaign_id,
            asdict(ingest),
            push.leads_selected,
        )
        return {
            "ok": True,
            "campaign_id": campaign_id,
            "hubspot": asdict(ingest),
            "smartlead_push": asdict(push),
        }
    finally:
        db.close()


@celery.task(name="worker.tasks.smartlead_active_stats_and_message_history")
def smartlead_active_stats_and_message_history() -> dict:
    """
    1) Por cada `campaign_id` distinto en BD entre leads ACTIVE con Smartlead: export CSV → estadísticas.
    2) Message-history por lead usando el `campaign_id` guardado en la fila.

    La campaña para nuevas altas la define `campaign_active` (no variables de entorno).
    """
    sl = _smartlead_optional()
    if sl is None:
        return {"ok": False, "error": "missing_smartlead_api_key"}

    hs = _hubspot_optional()
    db = create_session()
    try:
        campaign_ids = list_distinct_campaign_ids_for_active_smartlead_leads(db)
        stats_runs: list[dict[str, object]] = []
        for cid in campaign_ids:
            stats = sync_lead_statistics_from_smartlead_export(db, sl, hs, campaign_id=cid)
            stats_runs.append(asdict(stats))

        lead_ids = list_active_smartlead_lead_ids(db)
        history_summaries: list[dict[str, object]] = []
        for lid in lead_ids:
            r = sync_smartlead_message_history_for_lead(
                db,
                sl,
                hs,
                lead_id=lid,
                campaign_id=None,
            )
            history_summaries.append(
                {
                    "lead_id": str(lid),
                    "messages_upserted": r.messages_upserted,
                    "errors": r.errors,
                }
            )
        logger.info(
            "smartlead_active_stats campaign_ids=%s stats_runs=%s active_leads=%s",
            campaign_ids,
            len(stats_runs),
            len(lead_ids),
        )
        return {
            "ok": True,
            "campaign_ids_from_db": campaign_ids,
            "statistics_runs": stats_runs,
            "active_lead_count": len(lead_ids),
            "message_history": history_summaries,
        }
    finally:
        db.close()

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.integrations.hubspot.client import HubSpotClient, HubSpotClientError
from app.integrations.smartlead.client import SmartleadClient, SmartleadClientError
from app.integrations.smartlead.constants import (
    DEFAULT_ADD_LEAD_SETTINGS,
    SMARTLEAD_DEFAULT_CAMPAIGN_ID,
    SMARTLEAD_MAX_LEADS_PER_REQUEST,
)
from app.models.lead import Lead

logger = logging.getLogger(__name__)

GET_LEAD_BY_EMAIL_RETRY_SLEEP_SEC = 2.0


@dataclass
class SmartleadPushResult:
    campaign_id: str
    leads_selected: int = 0
    batches_posted: int = 0
    smartlead_added_count: int = 0
    smartlead_skipped_count: int = 0
    leads_resolved: int = 0
    leads_unresolved: int = 0
    db_updated: int = 0
    hubspot_patched: int = 0
    hubspot_failed: int = 0
    hubspot_skipped_no_contact: int = 0
    errors: list[str] = field(default_factory=list)


def _cf_str(key: str, value: Any) -> tuple[str, str] | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return key, "true" if value else "false"
    if isinstance(value, datetime):
        return key, value.isoformat()
    s = str(value).strip()
    if not s:
        return None
    return key, s


def lead_to_smartlead_lead_dict(lead: Lead) -> dict[str, Any]:
    """
    Campos estándar de Smartlead; el resto de columnas de `leads` va en `custom_fields`.
    """
    item: dict[str, Any] = {"email": lead.email}

    if lead.first_name:
        item["first_name"] = lead.first_name
    if lead.last_name:
        item["last_name"] = lead.last_name
    if lead.company_name:
        item["company_name"] = lead.company_name
    if lead.website:
        item["website"] = lead.website
        item["company_url"] = lead.website
    loc_parts = [p for p in (lead.address, lead.country) if p and str(p).strip()]
    if loc_parts:
        item["location"] = ", ".join(str(p) for p in loc_parts)
    if lead.linkedin_url:
        item["linkedin_profile"] = lead.linkedin_url

    cf: dict[str, str] = {}
    for key, val in (
        ("job_title", lead.job_title),
        ("last_email_subject", lead.last_email_subject),
        ("company_size", lead.company_size),
        ("company_category", lead.company_category),
        ("company_industry", lead.company_industry),
        ("lead_classification", lead.lead_classification),
        ("language", lead.language),
        ("seniority_level", lead.seniority_level),
        ("engagement_status", lead.engagement_status),
        ("sequence_status", lead.sequence_status),
        ("external_lead_id", lead.external_lead_id),
        ("hubspot_contact_id", lead.hubspot_contact_id),
        ("campaign_id", lead.campaign_id),
        ("total_opens", lead.total_opens),
        ("total_clicks", lead.total_clicks),
        ("total_replies", lead.total_replies),
        ("last_open_date", lead.last_open_date),
        ("last_click_date", lead.last_click_date),
        ("last_reply_date", lead.last_reply_date),
        ("last_contacted_date", lead.last_contacted_date),
        ("is_new_lead", lead.is_new_lead),
        ("is_qualified", lead.is_qualified),
        ("is_disqualified", lead.is_disqualified),
        ("invalid_email", lead.invalid_email),
        ("lead_score", lead.lead_score),
        ("last_event_type", lead.last_event_type),
        ("last_event_timestamp", lead.last_event_timestamp),
        ("event_source", lead.event_source),
        ("reply_type", lead.reply_type),
        ("linkedin_contacted", lead.linkedin_contacted),
        ("last_sequence_step", lead.last_sequence_step),
        ("internal_lead_id", str(lead.id)),
    ):
        pair = _cf_str(key, val)
        if pair:
            cf[pair[0]] = pair[1]

    if cf:
        item["custom_fields"] = cf
    return item


def _lead_payload_in_campaign(payload: dict[str, Any], campaign_id: str) -> bool:
    """Si Smartlead envía `lead_campaign_data`, exige que el lead esté en nuestra campaña."""
    raw = payload.get("lead_campaign_data")
    if not isinstance(raw, list) or len(raw) == 0:
        return True
    try:
        want = int(str(campaign_id).strip())
    except ValueError:
        return False
    for item in raw:
        if isinstance(item, dict):
            cid = item.get("campaign_id")
            if cid is not None and int(cid) == want:
                return True
    return False


def _id_from_lead_payload(payload: dict[str, Any]) -> str | None:
    lid = payload.get("id")
    if lid is None or lid == "":
        return None
    return str(lid).strip() or None


def resolve_smartlead_lead_id_for_campaign(
    client: SmartleadClient,
    email: str,
    campaign_id: str,
) -> str | None:
    """GET /leads/?email= — id del lead; opcionalmente valida `lead_campaign_data`."""
    payload = client.get_lead_by_email(email)
    if not payload:
        return None
    if not _lead_payload_in_campaign(payload, campaign_id):
        return None
    return _id_from_lead_payload(payload)


def push_new_leads_to_smartlead_campaign(
    session: Session,
    smartlead: SmartleadClient,
    hubspot: HubSpotClient | None,
    *,
    campaign_id: str = SMARTLEAD_DEFAULT_CAMPAIGN_ID,
    max_leads: int = SMARTLEAD_MAX_LEADS_PER_REQUEST,
) -> SmartleadPushResult:
    """
    Selecciona leads sin `smartlead_lead_id`, los envía a la campaña y resuelve el id con
    GET /api/v1/leads/?email= (sin listar toda la campaña). Luego actualiza DB + HubSpot.
    """
    result = SmartleadPushResult(campaign_id=campaign_id)
    cap = max(1, min(int(max_leads), SMARTLEAD_MAX_LEADS_PER_REQUEST * 25))

    stmt = (
        select(Lead)
        .where(Lead.smartlead_lead_id.is_(None))
        .where(Lead.invalid_email.is_(False))
        .order_by(Lead.created_at.asc())
        .limit(cap)
    )
    leads = list(session.scalars(stmt).all())
    result.leads_selected = len(leads)
    if not leads:
        return result

    for i in range(0, len(leads), SMARTLEAD_MAX_LEADS_PER_REQUEST):
        batch = leads[i : i + SMARTLEAD_MAX_LEADS_PER_REQUEST]
        body = {
            "lead_list": [lead_to_smartlead_lead_dict(L) for L in batch],
            "settings": dict(DEFAULT_ADD_LEAD_SETTINGS),
        }
        try:
            resp = smartlead.post_campaign_leads(campaign_id, body)
        except SmartleadClientError as e:
            msg = f"Smartlead POST lote falló ({campaign_id}): {e}"
            logger.warning(msg)
            result.errors.append(msg)
            continue

        result.batches_posted += 1
        result.smartlead_added_count += int(resp.get("added_count") or 0)
        result.smartlead_skipped_count += int(resp.get("skipped_count") or 0)

    def _resolve_sl_id(lead_email: str) -> str | None:
        sl_id = resolve_smartlead_lead_id_for_campaign(smartlead, lead_email, campaign_id)
        if sl_id:
            return sl_id
        time.sleep(GET_LEAD_BY_EMAIL_RETRY_SLEEP_SEC)
        return resolve_smartlead_lead_id_for_campaign(smartlead, lead_email, campaign_id)

    for lead in leads:
        sl_id = _resolve_sl_id(lead.email)
        if not sl_id:
            result.leads_unresolved += 1
            result.errors.append(
                f"Sin id Smartlead tras GET /leads/?email= para {lead.email} (campaña {campaign_id})."
            )
            continue

        result.leads_resolved += 1
        lead.smartlead_lead_id = sl_id
        lead.campaign_id = campaign_id
        lead.engagement_status = "CONTACTED"
        lead.sequence_status = "active"

        if hubspot and lead.hubspot_contact_id:
            try:
                hubspot.patch_contact_properties(
                    lead.hubspot_contact_id,
                    {
                        "engagement_status": "CONTACTED",
                        "sequence_status": "ACTIVE",
                        "smartlead_lead_id": sl_id,
                        "campaign_id": str(campaign_id),
                    },
                )
                result.hubspot_patched += 1
            except HubSpotClientError as e:
                result.hubspot_failed += 1
                err = f"HubSpot PATCH falló para {lead.email}: {e}"
                logger.warning(err)
                result.errors.append(err)
                try:
                    lead.error_flag = True
                    lead.error_message = (e.body or str(e))[:2000]
                except Exception:
                    pass
        elif not lead.hubspot_contact_id:
            result.hubspot_skipped_no_contact += 1

        result.db_updated += 1

    try:
        session.commit()
    except Exception as e:
        session.rollback()
        result.errors.append(f"Commit DB falló: {e}")
        logger.exception("smartlead push commit failed")

    return result

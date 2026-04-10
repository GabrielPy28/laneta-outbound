from __future__ import annotations

import io
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.integrations.hubspot.client import HubSpotClient, HubSpotClientError
from app.integrations.smartlead.client import SmartleadClient, SmartleadClientError
from app.models.lead import Lead
from app.models.lead_statistics import LeadStatistics

logger = logging.getLogger(__name__)

WEIGHT_OPEN = 5
WEIGHT_CLICK = 10
WEIGHT_REPLY = 20


def compute_lead_score(opens: int, clicks: int, replies: int) -> int:
    return WEIGHT_OPEN * opens + WEIGHT_CLICK * clicks + WEIGHT_REPLY * replies


def derive_last_event_type(opens: int, clicks: int, replies: int) -> str:
    if replies > 0:
        return "EMAIL_REPLIED"
    if clicks > 0:
        return "LINK_CLICKED"
    if opens > 0:
        return "EMAIL_OPENED"
    return "EMAIL_SENT"


def derive_engagement_status(opens: int, clicks: int, replies: int) -> str:
    """Valores alineados a `engagement_status` en HubSpot / properties.csv."""
    if replies > 0:
        return "REPLIED"
    if clicks > 0:
        return "CLICKED"
    if opens > 0:
        return "OPEN_NO_CLICK"
    return "NO_OPEN"


def _email_domain(email: str) -> str:
    parts = email.strip().lower().rsplit("@", 1)
    return parts[1] if len(parts) == 2 else ""


def _cell_int(val: Any) -> int:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return 0
    s = str(val).strip()
    if not s:
        return 0
    try:
        return int(float(s))
    except ValueError:
        return 0


def _sequence_step(val: Any) -> str | None:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    if isinstance(val, bool):
        return "true" if val else "false"
    if isinstance(val, int) and not isinstance(val, bool):
        return str(int(val))
    if isinstance(val, float):
        if val == int(val):
            return str(int(val))
        s = str(val).strip()
        return s or None
    s = str(val).strip()
    return s or None


def _cell_str(val: Any) -> str | None:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    s = str(val).strip()
    return s or None


def _cell_bool(val: Any) -> bool | None:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    if isinstance(val, bool):
        return val
    s = str(val).strip().lower()
    if s in ("true", "1", "yes", "y"):
        return True
    if s in ("false", "0", "no", "n"):
        return False
    return None


def _smartlead_row_id(val: Any) -> str | None:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    if isinstance(val, bool):
        return None
    if isinstance(val, float) and val == int(val):
        return str(int(val))
    if isinstance(val, int):
        return str(val)
    s = str(val).strip()
    if not s:
        return None
    try:
        return str(int(float(s)))
    except ValueError:
        return s


def _normalize_category_key(category: str | None) -> str | None:
    s = _cell_str(category)
    if not s:
        return None
    return s.strip().lower()


def _hubspot_sequence_status_value(local: str | None) -> str | None:
    """HubSpot enum: PAUSED, COMPLETED, ACTIVE, STOPPED (mayúsculas)."""
    if not local:
        return None
    key = str(local).strip().lower()
    return {
        "completed": "COMPLETED",
        "paused": "PAUSED",
        "active": "ACTIVE",
        "stopped": "STOPPED",
    }.get(key)


def _hubspot_lead_score_value(points: int) -> str:
    """
    En HubSpot, `lead_score` suele ser tipo **porcentaje**: la API espera una fracción 0–1
    (p. ej. `0.35` → 35 % en la UI). Los puntos locales son 5×opens + 10×clicks + 20×replies;
    si se envía `35` como número entero, el portal puede mostrar 3.500 %.
    """
    p = max(0.0, min(1.0, float(points) / 100.0))
    s = f"{p:.6f}".rstrip("0").rstrip(".")
    return s if s else "0"


def _hubspot_reply_type_from_category(category: str | None) -> str | None:
    """
    Mapea `category` del CSV Smartlead al enum `reply_type` del portal HubSpot.
    Si no hay mapeo conocido, no se envía la propiedad (evita INVALID_OPTION).
    """
    k = _normalize_category_key(category)
    if not k:
        return None
    return {
        "interested": "INTERESTED",
        "meeting request": "INTERESTED",
        "meeting booked": "COMPLETED",
        "not interested": "STOPPED",
        "follow up later": "PAUSED",
    }.get(k)


def _category_triggers_complete(category: str | None) -> bool:
    k = _normalize_category_key(category)
    if not k:
        return False
    return k in {"interested", "meeting request", "meeting booked"}


def _category_triggers_pause(category: str | None) -> bool:
    k = _normalize_category_key(category)
    if not k:
        return False
    return k in {"not interested", "follow up later"}


def _peers_same_domain(session: Session, campaign_id: str, domain: str) -> list[Lead]:
    dom = domain.strip().lower()
    if not dom:
        return []
    stmt = (
        select(Lead)
        .where(Lead.campaign_id == campaign_id)
        .where(Lead.smartlead_lead_id.is_not(None))
        .where(Lead.email.ilike(f"%@{dom}"))
    )
    return list(session.scalars(stmt).all())


def _domain_complete_dedup_key(lead: Lead) -> str:
    d = _email_domain(lead.email)
    return d if d else f"singleton:{lead.id}"


def _apply_org_manual_complete(
    session: Session,
    smartlead: SmartleadClient,
    hubspot: HubSpotClient | None,
    campaign_id: str,
    triggering_lead_id: uuid.UUID,
    by_sl_id: dict[str, Any],
    result: SmartleadLeadStatisticsSyncResult,
) -> None:
    """Marca `sequence_status=completed` mismo dominio + Smartlead manual-complete + HubSpot (excepto el lead disparador, que va en el PATCH principal)."""
    trigger = session.get(Lead, triggering_lead_id)
    if trigger is None:
        return
    dom = _email_domain(trigger.email)
    peers = _peers_same_domain(session, campaign_id, dom) if dom else [trigger]
    if not peers:
        peers = [trigger]

    for p in peers:
        p.sequence_status = "completed"

    for p in peers:
        sl = (p.smartlead_lead_id or "").strip()
        prow = by_sl_id.get(sl) if sl else None
        if prow is not None:
            map_id = _cell_str(prow.get("campaign_lead_map_id"))
            if map_id:
                try:
                    smartlead.post_manual_complete_campaign_lead(campaign_id, map_id)
                except SmartleadClientError as e:
                    msg = f"Smartlead manual-complete falló ({p.email}, map {map_id}): {e}"
                    logger.warning(msg)
                    result.errors.append(msg)

        if p.id == triggering_lead_id:
            continue
        if hubspot and p.hubspot_contact_id:
            try:
                hubspot.patch_contact_properties(
                    p.hubspot_contact_id,
                    {"sequence_status": "COMPLETED"},
                )
                result.hubspot_patched += 1
            except HubSpotClientError as e:
                result.hubspot_failed += 1
                msg = f"HubSpot PATCH sequence_status (complete) {p.email}: {e}"
                logger.warning(msg)
                result.errors.append(msg)


@dataclass
class SmartleadLeadStatisticsSyncResult:
    campaign_id: str
    export_rows: int = 0
    matched_leads: int = 0
    statistics_upserted: int = 0
    hubspot_patched: int = 0
    hubspot_failed: int = 0
    hubspot_skipped_no_contact: int = 0
    errors: list[str] = field(default_factory=list)


def sync_lead_statistics_from_smartlead_export(
    session: Session,
    smartlead: SmartleadClient,
    hubspot: HubSpotClient | None,
    *,
    campaign_id: str,
) -> SmartleadLeadStatisticsSyncResult:
    """
    CSV leads-export: métricas, `category` → `reply_type` (HubSpot), `status` / `is_interested`,
    engagement por conteos. Con `reply_count` y categoría positiva: manual-complete + completed
    en mismo dominio; con negativa: pause solo ese lead + paused.
    """
    cid = str(campaign_id).strip()
    result = SmartleadLeadStatisticsSyncResult(campaign_id=cid)
    now = datetime.now(timezone.utc)

    try:
        raw = smartlead.get_campaign_leads_export_csv(cid, timeout_seconds=120.0)
    except SmartleadClientError as e:
        result.errors.append(str(e))
        return result

    if not raw.strip():
        result.errors.append("Export Smartlead vacío.")
        return result

    df = pd.read_csv(io.BytesIO(raw))
    result.export_rows = len(df.index)
    if result.export_rows == 0:
        return result

    required = {
        "id",
        "open_count",
        "click_count",
        "reply_count",
        "last_email_sequence_sent",
        "status",
        "is_interested",
        "category",
        "campaign_lead_map_id",
    }
    missing = required - set(df.columns)
    if missing:
        result.errors.append(f"CSV sin columnas: {sorted(missing)}")
        return result

    by_sl_id: dict[str, Any] = {}
    for _, row in df.iterrows():
        sl_id = _smartlead_row_id(row.get("id"))
        if sl_id:
            by_sl_id[sl_id] = row

    stmt = (
        select(Lead)
        .where(Lead.smartlead_lead_id.is_not(None))
        .where(Lead.campaign_id == cid)
    )
    leads = list(session.scalars(stmt).all())

    completed_domain_keys: set[str] = set()

    for lead in leads:
        sl_id = (lead.smartlead_lead_id or "").strip()
        if not sl_id or sl_id not in by_sl_id:
            continue

        result.matched_leads += 1
        row = by_sl_id[sl_id]
        opens = _cell_int(row.get("open_count"))
        clicks = _cell_int(row.get("click_count"))
        replies = _cell_int(row.get("reply_count"))
        last_step = _sequence_step(row.get("last_email_sequence_sent"))
        interested = _cell_bool(row.get("is_interested"))
        category = _cell_str(row.get("category"))

        score = compute_lead_score(opens, clicks, replies)
        event_type = derive_last_event_type(opens, clicks, replies)
        engagement = derive_engagement_status(opens, clicks, replies)

        stat = session.get(LeadStatistics, lead.id)
        if stat is None:
            stat = LeadStatistics(id_lead=lead.id)
            session.add(stat)
        stat.campaign_id = cid
        stat.last_sequence_step = last_step
        stat.total_opens = opens
        stat.total_clicks = clicks
        stat.total_replies = replies
        stat.lead_score = score
        stat.last_event_type = event_type
        stat.updated_at = now

        lead.total_opens = opens
        lead.total_clicks = clicks
        lead.total_replies = replies
        lead.lead_score = score
        lead.last_event_type = event_type
        lead.last_sequence_step = last_step
        lead.engagement_status = engagement
        if category:
            lead.reply_type = category[:64]
        if interested is not None:
            lead.is_qualified = interested

        if replies > 0 and _category_triggers_complete(category):
            dk = _domain_complete_dedup_key(lead)
            if dk not in completed_domain_keys:
                completed_domain_keys.add(dk)
                _apply_org_manual_complete(session, smartlead, hubspot, cid, lead.id, by_sl_id, result)
        elif replies > 0 and _category_triggers_pause(category):
            lead.sequence_status = "paused"
            try:
                smartlead.pause_campaign_lead(cid, sl_id)
            except SmartleadClientError as e:
                msg = f"Smartlead pause falló ({lead.email}): {e}"
                logger.warning(msg)
                result.errors.append(msg)

        result.statistics_upserted += 1

        if hubspot and lead.hubspot_contact_id:
            props: dict[str, str] = {
                "total_opens": str(opens),
                "total_clicks": str(clicks),
                "lead_score": _hubspot_lead_score_value(score),
                "engagement_status": engagement,
            }
            if last_step is not None:
                props["last_sequence_step"] = last_step
            props["last_event_type"] = event_type
            rt_hs = _hubspot_reply_type_from_category(category)
            if rt_hs is not None:
                props["reply_type"] = rt_hs
            if interested is not None:
                props["is_qualified"] = "true" if interested else "false"
            seq_hs = _hubspot_sequence_status_value(lead.sequence_status)
            if seq_hs is not None:
                props["sequence_status"] = seq_hs
            try:
                hubspot.patch_contact_properties(lead.hubspot_contact_id, props)
                result.hubspot_patched += 1
            except HubSpotClientError as e:
                result.hubspot_failed += 1
                msg = f"HubSpot PATCH falló para {lead.email}: {e}"
                logger.warning(msg)
                result.errors.append(msg)
        elif not lead.hubspot_contact_id:
            result.hubspot_skipped_no_contact += 1

    try:
        session.commit()
    except Exception as e:
        session.rollback()
        result.errors.append(f"Commit DB falló: {e}")
        logger.exception("smartlead lead statistics commit failed")

    return result

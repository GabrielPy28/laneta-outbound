from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.integrations.hubspot.client import HubSpotClient, HubSpotClientError
from app.integrations.smartlead.client import SmartleadClient, SmartleadClientError
from app.integrations.smartlead.constants import SMARTLEAD_DEFAULT_CAMPAIGN_ID
from app.models.lead import Lead
from app.models.lead_message_history import LeadMessageHistory
from app.services.email_body_html import extract_inbound_reply_html, re_reply_subject

logger = logging.getLogger(__name__)


@dataclass
class MessageHistorySyncResult:
    lead_id: str
    messages_upserted: int = 0
    has_inbound_reply: bool = False
    reply_intent: str | None = None
    hubspot_patched: bool = False
    smartlead_paused_count: int = 0
    errors: list[str] = field(default_factory=list)


def _parse_dt(val: Any) -> datetime | None:
    if val is None:
        return None
    s = str(val).strip()
    if not s:
        return None
    try:
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return None


def _hubspot_dt(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat().replace("+00:00", "Z")


def _message_sort_key(m: dict[str, Any]) -> datetime:
    for key in ("sent_at", "received_at", "opened_at", "time"):
        if dt := _parse_dt(m.get(key)):
            return dt
    return datetime.min.replace(tzinfo=timezone.utc)


def _seq_fallback(entry: dict[str, Any]) -> str | None:
    raw = entry.get("email_seq_number")
    if raw is None:
        return None
    s = str(raw).strip()
    return s or None


def _normalize_smartlead_history_entry(entry: dict[str, Any]) -> dict[str, Any] | None:
    """
    Formato real Smartlead (`history[]`): type SENT | REPLY, `time`, `message_id`, etc.
    → forma interna compatible con el bucle que espera id/direction/sent_at/received_at.
    """
    mid_raw = entry.get("message_id")
    if mid_raw is None or str(mid_raw).strip() == "":
        return None
    mid = str(mid_raw).strip()

    type_upper = str(entry.get("type") or "").strip().upper()
    t = _parse_dt(entry.get("time"))
    subject_raw = entry.get("subject")
    subject = str(subject_raw).strip() if subject_raw is not None else ""
    subject = subject or None
    body = entry.get("email_body")
    body_str = body if isinstance(body, str) else None
    seq_fb = _seq_fallback(entry)

    if type_upper == "SENT":
        return {
            "id": mid,
            "direction": "outbound",
            "subject": subject,
            "sent_at": t,
            "opened_at": None,
            "received_at": None,
            "email_body": body_str,
            "sequence_step_fallback": None,
        }
    if type_upper == "REPLY":
        return {
            "id": mid,
            "direction": "inbound",
            "subject": subject,
            "sent_at": None,
            "opened_at": None,
            "received_at": t,
            "email_body": body_str,
            "sequence_step_fallback": seq_fb,
        }
    return None


def _coerce_messages_from_smartlead_payload(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Acepta `history` (API actual) o `messages` (formato legado interno / mocks)."""
    history = payload.get("history")
    if isinstance(history, list) and history:
        normalized: list[dict[str, Any]] = []
        for item in history:
            if not isinstance(item, dict):
                continue
            row = _normalize_smartlead_history_entry(item)
            if row:
                normalized.append(row)
        return sorted(normalized, key=_message_sort_key)

    raw = payload.get("messages")
    if isinstance(raw, list) and raw:
        coerced: list[dict[str, Any]] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            c = dict(item)
            if "sequence_step_fallback" not in c:
                c["sequence_step_fallback"] = _seq_fallback(c)
            coerced.append(c)
        return sorted(coerced, key=_message_sort_key)
    return []


def sync_smartlead_message_history_for_lead(
    session: Session,
    smartlead: SmartleadClient,
    hubspot: HubSpotClient | None,
    *,
    lead_id: uuid.UUID,
    campaign_id: str | None = None,
) -> MessageHistorySyncResult:
    """
    Descarga message-history de Smartlead, persiste en `lead_message_history` (HTML; inbound sin cita),
    actualiza campos locales del lead y HubSpot.
    """
    lid_str = str(lead_id)
    result = MessageHistorySyncResult(lead_id=lid_str)

    lead = session.get(Lead, lead_id)
    if lead is None:
        result.errors.append(f"Lead no encontrado: {lead_id}")
        return result

    sl_id = (lead.smartlead_lead_id or "").strip()
    if not sl_id:
        result.errors.append("El lead no tiene smartlead_lead_id.")
        return result

    cid = (campaign_id or lead.campaign_id or SMARTLEAD_DEFAULT_CAMPAIGN_ID).strip()
    if not cid:
        result.errors.append("No hay campaign_id (ni en el lead ni por defecto).")
        return result

    try:
        payload = smartlead.get_lead_message_history(cid, sl_id)
    except SmartleadClientError as e:
        msg = f"Smartlead message-history falló: {e}"
        logger.warning(msg)
        result.errors.append(msg)
        return result

    sorted_raw = _coerce_messages_from_smartlead_payload(payload)
    if not sorted_raw:
        return result

    max_opened: datetime | None = None
    last_outbound_subject: str | None = None
    last_inbound_subject: str | None = None
    last_inbound_at: datetime | None = None

    for m in sorted_raw:
        if not isinstance(m, dict):
            continue
        mid = str(m.get("id") or "").strip()
        if not mid:
            continue

        direction = str(m.get("direction") or "").strip().lower() or "unknown"
        raw_subject = str(m.get("subject") or "").strip() or None
        seq_fb = str(m.get("sequence_step_fallback") or "").strip() or None
        sent_at = _parse_dt(m.get("sent_at"))
        opened_at = _parse_dt(m.get("opened_at"))
        received_at = _parse_dt(m.get("received_at"))
        body_html = m.get("email_body")

        if direction == "inbound":
            subject = re_reply_subject(last_outbound_subject) or raw_subject or seq_fb
            body_store = extract_inbound_reply_html(body_html if isinstance(body_html, str) else None)
        else:
            subject = raw_subject
            if isinstance(body_html, str) and body_html.strip():
                body_store = body_html.strip()
            else:
                body_store = None

        row = session.scalar(
            select(LeadMessageHistory).where(
                LeadMessageHistory.lead_id == lead.id,
                LeadMessageHistory.message_id == mid,
            )
        )
        if row is None:
            row = LeadMessageHistory(
                lead_id=lead.id,
                message_id=mid,
            )
            session.add(row)

        row.subject = subject
        row.direction = direction
        row.sent_at = sent_at
        row.opened_at = opened_at
        row.received_at = received_at
        row.email_body = body_store
        row.reply_intent = None
        result.messages_upserted += 1

        if opened_at and (max_opened is None or opened_at > max_opened):
            max_opened = opened_at

        if direction == "outbound":
            last_outbound_subject = subject or last_outbound_subject
        if direction == "inbound":
            last_inbound_subject = subject or last_inbound_subject
            last_inbound_at = received_at or sent_at or last_inbound_at

    has_inbound = any(
        isinstance(m, dict) and str(m.get("direction") or "").strip().lower() == "inbound" for m in sorted_raw
    )
    result.has_inbound_reply = has_inbound
    result.reply_intent = None

    lead.last_open_date = max_opened or lead.last_open_date
    if last_inbound_at:
        lead.last_reply_date = last_inbound_at
    if last_outbound_subject:
        lead.last_email_subject = last_outbound_subject[:512]
    if hubspot and lead.hubspot_contact_id:
        hs_props: dict[str, str] = {}
        if max_opened:
            hs_props["hs_email_last_open_date"] = _hubspot_dt(max_opened)
        if last_outbound_subject:
            hs_props["nombre_ultimo_mensaje"] = last_outbound_subject[:512]
        if has_inbound and last_inbound_subject:
            hs_props["ultima_respuesta_de_mensaje"] = last_inbound_subject[:512]
        if hs_props:
            try:
                hubspot.patch_contact_properties(lead.hubspot_contact_id, hs_props)
                result.hubspot_patched = True
            except HubSpotClientError as e:
                err = f"HubSpot PATCH falló: {e}"
                logger.warning(err)
                result.errors.append(err)
                try:
                    lead.error_flag = True
                    lead.error_message = (e.body or str(e))[:2000]
                except Exception:
                    pass

    try:
        session.commit()
    except Exception as e:
        session.rollback()
        result.errors.append(f"Commit DB falló: {e}")
        logger.exception("message history sync commit failed")

    return result

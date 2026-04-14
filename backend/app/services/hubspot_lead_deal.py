from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.integrations.hubspot.client import HubSpotClient, HubSpotClientError
from app.models.lead import Lead
from app.models.lead_deal import LeadDeal

# Pipeline La Neta — internal dealstage ids
DEAL_STAGE_CONTACTADO = "1340627366"
DEAL_STAGE_CUALIFICADO = "1340627367"
DEAL_STAGE_REUNION_AGENDADA = "1340627368"
DEAL_STAGE_CERRADO_GANADO = "1340627371"
DEAL_STAGE_CERRADO_PERDIDO = "1340627372"

DEAL_STAGE_ID_TO_NAME: dict[str, str] = {
    "1340627365": "Prospecto Nuevo",
    DEAL_STAGE_CONTACTADO: "Contactado",
    DEAL_STAGE_CUALIFICADO: "Cualificado",
    DEAL_STAGE_REUNION_AGENDADA: "Reunion Agendada",
    "1340627369": "Propuesta Enviada",
    "1340627370": "Negociacion",
    DEAL_STAGE_CERRADO_GANADO: "Cerrado Ganado",
    DEAL_STAGE_CERRADO_PERDIDO: "Cerrado Perdido",
    "1340627373": "Nurture",
}


def _norm_category(category: str | None) -> str | None:
    if category is None:
        return None
    s = str(category).strip().lower()
    return s or None


def _sequence_step_int(step: str | None) -> int | None:
    if step is None:
        return None
    s = str(step).strip()
    if not s:
        return None
    try:
        return int(float(s))
    except ValueError:
        return None


def resolve_deal_stage_id(
    *,
    sequence_status: str | None,
    category: str | None,
    opens: int,
    clicks: int,
    replies: int,
    last_sequence_step: str | None,
    last_event_type: str | None,
) -> str | None:
    """
    Prioridad: terminal (ganado/perdido) → reunión por categoría → cualificado (interés + engagement)
    → Contactado si primer envío (EMAIL_SENT + paso 1, o cualquier paso ≥1 mientras el último evento sea EMAIL_SENT)
    → Contactado si hay opens/clicks/replies sin regla superior.

    Propuesta / Negociación / Nurture no se asignan aquí.
    """
    seq = (sequence_status or "").strip().lower()
    if seq == "completed":
        return DEAL_STAGE_CERRADO_GANADO
    if seq == "paused":
        return DEAL_STAGE_CERRADO_PERDIDO

    cat = _norm_category(category)
    touches = max(0, int(opens)) + max(0, int(clicks)) + max(0, int(replies))
    ev = (last_event_type or "").strip().upper().replace(" ", "_")

    if cat == "meeting request":
        return DEAL_STAGE_REUNION_AGENDADA

    if cat in {"interested", "information request"} and touches > 0:
        return DEAL_STAGE_CUALIFICADO

    # Contactado: primer toque de secuencia (p. ej. EMAIL_SENT + paso 1) o siguientes envíos sin apertura aún
    if ev == "EMAIL_SENT":
        si = _sequence_step_int(last_sequence_step)
        if si is not None and si >= 1:
            return DEAL_STAGE_CONTACTADO

    if touches > 0:
        return DEAL_STAGE_CONTACTADO

    return None


def _first_deal_id_from_contact_payload(payload: dict[str, Any]) -> str | None:
    assoc = payload.get("associations") or {}
    for key in ("deals", "deal"):
        raw = assoc.get(key)
        if not isinstance(raw, dict):
            continue
        results = raw.get("results") or []
        if not results:
            continue
        first = results[0]
        if isinstance(first, dict) and first.get("id") is not None:
            s = str(first["id"]).strip()
            if s:
                return s
    return None


@dataclass
class HubSpotLeadDealSyncResult:
    updated: bool = False
    skipped_no_contact: bool = False
    skipped_no_deal: bool = False
    skipped_no_stage_rule: bool = False
    hubspot_deal_id: str | None = None
    dealstage_id: str | None = None
    errors: list[str] = field(default_factory=list)


def sync_hubspot_deal_stage_for_lead(
    session: Session,
    hubspot: HubSpotClient,
    lead: Lead,
    *,
    category: str | None = None,
    opens: int | None = None,
    clicks: int | None = None,
    replies: int | None = None,
    last_sequence_step: str | None = None,
    last_event_type: str | None = None,
) -> HubSpotLeadDealSyncResult:
    out = HubSpotLeadDealSyncResult()
    cid = (lead.hubspot_contact_id or "").strip()
    if not cid:
        out.skipped_no_contact = True
        return out

    o = lead.total_opens if opens is None else int(opens)
    c = lead.total_clicks if clicks is None else int(clicks)
    r = lead.total_replies if replies is None else int(replies)
    step = lead.last_sequence_step if last_sequence_step is None else last_sequence_step
    ev = lead.last_event_type if last_event_type is None else last_event_type
    cat = category if category is not None else lead.reply_type

    stage_id = resolve_deal_stage_id(
        sequence_status=lead.sequence_status,
        category=cat,
        opens=o,
        clicks=c,
        replies=r,
        last_sequence_step=step,
        last_event_type=ev,
    )
    if stage_id is None:
        out.skipped_no_stage_rule = True
        return out

    try:
        contact_json = hubspot.get_contact_with_associations(cid)
    except HubSpotClientError as e:
        out.errors.append(f"HubSpot GET contact {cid} ({lead.email}): {e}")
        return out

    deal_id = _first_deal_id_from_contact_payload(contact_json)
    if not deal_id:
        out.skipped_no_deal = True
        return out
    out.hubspot_deal_id = deal_id

    try:
        deal_json = hubspot.patch_deal_properties(deal_id, {"dealstage": stage_id})
    except HubSpotClientError as e:
        out.errors.append(f"HubSpot PATCH deal {deal_id} ({lead.email}): {e}")
        return out

    out.updated = True
    out.dealstage_id = stage_id

    props = deal_json.get("properties") or {}
    dealname = props.get("dealname")
    stage_raw = props.get("dealstage")
    stage_key = str(stage_raw).strip() if stage_raw is not None else stage_id
    stage_name = DEAL_STAGE_ID_TO_NAME.get(stage_key, stage_key)

    cprops = contact_json.get("properties") or {}
    first = cprops.get("firstname") or lead.first_name
    email = cprops.get("email") or lead.email

    now = datetime.now(timezone.utc)
    row = session.get(LeadDeal, lead.id)
    if row is None:
        row = LeadDeal(id_lead=lead.id)
        session.add(row)
    row.first_name = str(first)[:255] if first is not None else None
    row.email = str(email)[:320] if email is not None else None
    row.dealname = str(dealname)[:512] if dealname is not None else None
    row.dealstage_name = str(stage_name)[:128] if stage_name is not None else None
    row.updated_at = now

    # Mismo lead puede sincronizarse dos veces en un commit (p. ej. fila principal + peer en manual-complete).
    session.flush()

    return out


def merge_deal_sync_into_stats_result(agg: Any, r: HubSpotLeadDealSyncResult) -> None:
    if r.updated:
        agg.hubspot_deals_patched = int(getattr(agg, "hubspot_deals_patched", 0)) + 1
    elif r.errors:
        agg.hubspot_deals_failed = int(getattr(agg, "hubspot_deals_failed", 0)) + 1
    elif r.skipped_no_deal:
        agg.hubspot_deals_skipped_no_deal = int(getattr(agg, "hubspot_deals_skipped_no_deal", 0)) + 1
    agg.errors.extend(r.errors)

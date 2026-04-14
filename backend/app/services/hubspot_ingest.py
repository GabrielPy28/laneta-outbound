from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.integrations.hubspot.client import HubSpotClient, HubSpotClientError
from app.models.lead import Lead
from app.services.campaign_active import get_effective_smartlead_campaign_id

logger = logging.getLogger(__name__)


@dataclass
class HubSpotNewLeadsSyncResult:
    pages_fetched: int = 0
    contacts_scanned: int = 0
    created: int = 0
    updated: int = 0
    skipped_no_email: int = 0
    hubspot_marked_done: int = 0
    hubspot_mark_failed: int = 0
    errors: list[str] = field(default_factory=list)


def _s(v: Any) -> str | None:
    if v is None:
        return None
    t = str(v).strip()
    return t or None


def _int(v: Any) -> int | None:
    s = _s(v)
    if s is None:
        return None
    try:
        return int(float(s))
    except ValueError:
        return None


def _dt(v: Any) -> datetime | None:
    s = _s(v)
    if s is None:
        return None
    try:
        t = s.replace("Z", "+00:00") if s.endswith("Z") else s
        return datetime.fromisoformat(t)
    except ValueError:
        return None


def _apply_hubspot_properties(lead: Lead, props: dict[str, Any], *, hubspot_id: str) -> None:
    lead.hubspot_contact_id = hubspot_id
    lead.email = _s(props.get("email")) or lead.email

    if fn := _s(props.get("firstname")):
        lead.first_name = fn
    if ln := _s(props.get("lastname")):
        lead.last_name = ln
    if co := _s(props.get("company")):
        lead.company_name = co
    if jt := _s(props.get("jobtitle")):
        lead.job_title = jt
    if ws := _s(props.get("website")):
        lead.website = ws

    if subj := _s(props.get("nombre_ultimo_mensaje")):
        lead.last_email_subject = subj[:512]
    elif subj := _s(props.get("hs_email_last_email_name")):
        lead.last_email_subject = subj[:512]

    if ad := _s(props.get("address")):
        lead.address = ad[:512]
    else:
        addr_parts = [
            _s(props.get("city")),
            _s(props.get("state")),
            _s(props.get("zip")),
        ]
        joined = ", ".join(p for p in addr_parts if p)
        if joined:
            lead.address = joined[:512]

    if c := _s(props.get("country")):
        lead.country = c
    if p := _s(props.get("pais")):
        lead.country = p
    if li := _s(props.get("hs_linkedin_url")):
        lead.linkedin_url = li

    if d := _dt(props.get("hs_email_last_open_date")):
        lead.last_open_date = d
    if d := _dt(props.get("hs_email_last_click_date")):
        lead.last_click_date = d

    if ext := _s(props.get("external_lead_id")):
        lead.external_lead_id = ext
    if cid := _s(props.get("campaign_id")):
        lead.campaign_id = cid

    for key, attr in (
        ("engagement_status", "engagement_status"),
        ("sequence_status", "sequence_status"),
        ("lead_classification", "lead_classification"),
        ("company_category", "company_category"),
        ("company_industry", "company_industry"),
        ("language", "language"),
        ("seniority_level", "seniority_level"),
    ):
        if val := _s(props.get(key)):
            setattr(lead, attr, val)

    if cs := _int(props.get("company_size")):
        lead.company_size = cs
    if ls := _int(props.get("lead_score")):
        lead.lead_score = ls


def _find_existing_lead(session: Session, *, hubspot_id: str, email: str) -> Lead | None:
    row = session.scalar(select(Lead).where(Lead.hubspot_contact_id == hubspot_id))
    if row:
        return row
    return session.scalar(select(Lead).where(Lead.email == email))


def sync_new_leads_from_hubspot(session: Session, client: HubSpotClient) -> HubSpotNewLeadsSyncResult:
    """
    Busca contactos con is_new_lead=true, hace upsert en DB y marca is_new_lead=false en HubSpot.
    Pagina hasta agotar resultados.
    """
    result = HubSpotNewLeadsSyncResult()
    after: str | None = None
    fallback_campaign_id = get_effective_smartlead_campaign_id(session)

    while True:
        try:
            payload = client.search_contacts_is_new_lead(limit=100, after=after)
        except HubSpotClientError as e:
            msg = f"HubSpot search error: {e} (status={e.status_code})"
            logger.exception(msg)
            result.errors.append(msg)
            return result

        result.pages_fetched += 1
        contacts = payload.get("results") or []

        for item in contacts:
            result.contacts_scanned += 1
            hubspot_id = str(item.get("id", "")).strip()
            props = item.get("properties") or {}
            email = _s(props.get("email"))
            if not hubspot_id:
                result.errors.append("Contacto sin id de HubSpot; omitido.")
                continue
            if not email:
                result.skipped_no_email += 1
                result.errors.append(f"Contacto HubSpot {hubspot_id} sin email; omitido.")
                continue

            existing = _find_existing_lead(session, hubspot_id=hubspot_id, email=email)
            created = existing is None
            try:
                if existing is None:
                    lead = Lead(email=email, hubspot_contact_id=hubspot_id)
                    _apply_hubspot_properties(lead, props, hubspot_id=hubspot_id)
                    if not lead.campaign_id:
                        lead.campaign_id = fallback_campaign_id
                    if not lead.engagement_status:
                        lead.engagement_status = "NEW"
                    session.add(lead)
                else:
                    lead = existing
                    if lead.hubspot_contact_id and lead.hubspot_contact_id != hubspot_id:
                        msg = (
                            f"Email {email} ya existe con otro hubspot_contact_id "
                            f"({lead.hubspot_contact_id} vs {hubspot_id}); omitido."
                        )
                        result.errors.append(msg)
                        continue
                    _apply_hubspot_properties(lead, props, hubspot_id=hubspot_id)
                    if not lead.campaign_id:
                        lead.campaign_id = fallback_campaign_id
                    if not lead.engagement_status:
                        lead.engagement_status = "NEW"

                session.flush()
                lead.external_lead_id = str(lead.id)
                session.commit()
            except IntegrityError as e:
                session.rollback()
                err = f"Integridad DB para {email}: {e.orig}"
                logger.warning(err)
                result.errors.append(err)
                continue
            except Exception as e:
                session.rollback()
                err = f"Error guardando {email}: {e}"
                logger.exception(err)
                result.errors.append(err)
                continue

            if created:
                result.created += 1
            else:
                result.updated += 1

            try:
                client.mark_contact_ingested(hubspot_id, str(lead.id))
                result.hubspot_marked_done += 1
            except HubSpotClientError as e:
                result.hubspot_mark_failed += 1
                err = f"No se pudo actualizar HubSpot (is_new_lead / external_lead_id) para {hubspot_id}: {e}"
                logger.warning(err)
                result.errors.append(err)
                try:
                    lead = session.scalar(
                        select(Lead).where(Lead.hubspot_contact_id == hubspot_id)
                    )
                    if lead:
                        lead.error_flag = True
                        lead.error_message = (e.body or str(e))[:2000]
                        session.commit()
                except Exception:
                    session.rollback()
                    logger.exception("No se pudo persistir error_flag tras fallo HubSpot")

        paging = (payload.get("paging") or {}).get("next") or {}
        after = paging.get("after")
        if not after:
            break

    return result

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo

from app.core.config import Settings
from app.integrations.google_calendar.client import insert_calendar_event
from app.integrations.hubspot.client import LIST_MEETINGS_PAGE_LIMIT, HubSpotClient
from app.integrations.hubspot.constants import CONTACT_PROPERTIES_FOR_MEETING_LIST
from app.services.hubspot_calls import hubspot_call_timestamp_ms
from app.services.hubspot_lead_deal import (
    DEAL_STAGE_REUNION_AGENDADA,
    _first_deal_id_from_contact_payload,
)

MEXICO_CITY_TZ = ZoneInfo("America/Mexico_City")


def _hubspot_meeting_time_utc_z(dt: datetime) -> str:
    u = dt.astimezone(timezone.utc) if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    return u.strftime("%Y-%m-%dT%H:%M:%S.000Z")


def _as_mexico_city_wall_time(dt: datetime) -> datetime:
    """
    Interpreta el reloj recibido como hora local de CDMX.

    Esto evita desplazamientos cuando el cliente envía `Z` aunque la intención de negocio
    sea "10:30 hora MX". Conserva YYYY-mm-dd HH:MM:SS y fija tz America/Mexico_City.
    """
    return dt.replace(tzinfo=MEXICO_CITY_TZ)


def _s(v: Any) -> str | None:
    if v is None:
        return None
    t = str(v).strip()
    return t if t else None


def _contact_display_name(
    firstname: str | None,
    lastname: str | None,
    fallback_email: str,
) -> str:
    parts = [p for p in ((firstname or "").strip(), (lastname or "").strip()) if p]
    if parts:
        return " ".join(parts)
    local = fallback_email.strip().split("@", 1)[0]
    return local or fallback_email.strip()


@dataclass
class CreateMeetingLinkedResult:
    meeting_id: str
    hs_meeting_title: str | None
    hs_meeting_body: str | None
    hs_internal_meeting_notes: str | None
    hs_meeting_external_url: str | None
    hs_meeting_start_time: str | None
    hs_meeting_end_time: str | None
    hubspot_contact_id: str
    hubspot_deal_id: str | None
    calendar_html_link: str


MAX_MEETING_LIST_PAGES = 500
MEETING_LIST_INITIAL_AFTER = "108441413243"


def create_meeting_with_calendar_and_contact(
    settings: Settings,
    hubspot: HubSpotClient,
    *,
    crm_contact_id: str,
    email: str,
    title: str,
    description: str,
    additional_notes: str | None,
    start_time: datetime,
    end_time: datetime,
) -> CreateMeetingLinkedResult:
    """
    1) Localiza contacto por `crm_contact_id` (y deal si existe).
    2) Crea evento en Google Calendar (htmlLink).
    3) Crea reunión en HubSpot con URL externa.
    4) Si hay deal, actualiza dealstage a Reunión agendada.
    5) Asocia reunión ↔ contacto (default).
    """
    start_time_mx = _as_mexico_city_wall_time(start_time)
    end_time_mx = _as_mexico_city_wall_time(end_time)

    search = hubspot.search_contacts_by_property_eq(
        property_name="crm_contact_id",
        value=crm_contact_id.strip(),
        limit=5,
        properties=("crm_contact_id", "firstname", "lastname", "email"),
    )
    results = search.get("results") or []
    if not results:
        raise LookupError(f"No hay contacto en HubSpot con crm_contact_id={crm_contact_id!r}.")

    hubspot_contact_id = str(results[0].get("id", "")).strip()
    if not hubspot_contact_id:
        raise LookupError("Resultado de búsqueda sin id de contacto.")

    sp0 = results[0].get("properties") if isinstance(results[0].get("properties"), dict) else {}
    fn = _s(sp0.get("firstname"))
    ln = _s(sp0.get("lastname"))
    display_name = _contact_display_name(fn, ln, email)

    assoc_payload = hubspot.get_contact_with_associations(
        hubspot_contact_id,
        associations=("deals", "deal"),
        properties=("firstname", "lastname"),
    )
    deal_id = _first_deal_id_from_contact_payload(assoc_payload)

    cal_event = insert_calendar_event(
        settings,
        title=title.strip(),
        description=description.strip(),
        contact_email=email.strip(),
        contact_display_name=display_name,
        additional_notes=additional_notes,
        start_time=start_time_mx,
        end_time=end_time_mx,
    )
    hangout = cal_event.get("hangoutLink") if isinstance(cal_event, dict) else None
    html_link = cal_event.get("htmlLink") if isinstance(cal_event, dict) else None
    calendar_link = hangout or html_link
    html_link_s = str(calendar_link).strip() if calendar_link else ""
    if not html_link_s:
        raise ValueError("Google Calendar no devolvió hangoutLink/htmlLink en la respuesta.")

    notes = (additional_notes.strip() if additional_notes else "") or ""

    meeting = hubspot.create_meeting(
        properties={
            "hs_timestamp": hubspot_call_timestamp_ms(start_time_mx),
            "hs_meeting_title": title.strip(),
            "hs_meeting_body": description.strip(),
            "hs_internal_meeting_notes": notes,
            "hs_meeting_external_url": html_link_s,
            "hs_meeting_location": "Google Meet",
            "hs_meeting_start_time": _hubspot_meeting_time_utc_z(start_time_mx),
            "hs_meeting_end_time": _hubspot_meeting_time_utc_z(end_time_mx),
        }
    )

    meeting_id = str(meeting.get("id", "")).strip()
    if not meeting_id:
        raise ValueError("HubSpot no devolvió id de reunión.")

    if deal_id:
        hubspot.patch_deal_properties(deal_id, {"dealstage": DEAL_STAGE_REUNION_AGENDADA})

    hubspot.associate_meeting_with_contact_default(
        meeting_id=meeting_id,
        contact_id=hubspot_contact_id,
    )

    mp = meeting.get("properties") if isinstance(meeting.get("properties"), dict) else {}

    return CreateMeetingLinkedResult(
        meeting_id=meeting_id,
        hs_meeting_title=_s(mp.get("hs_meeting_title")),
        hs_meeting_body=_s(mp.get("hs_meeting_body")),
        hs_internal_meeting_notes=_s(mp.get("hs_internal_meeting_notes")),
        hs_meeting_external_url=_s(mp.get("hs_meeting_external_url")),
        hs_meeting_start_time=_s(mp.get("hs_meeting_start_time")),
        hs_meeting_end_time=_s(mp.get("hs_meeting_end_time")),
        hubspot_contact_id=hubspot_contact_id,
        hubspot_deal_id=deal_id,
        calendar_html_link=html_link_s,
    )


@dataclass
class MeetingListItem:
    firstname: str | None
    lastname: str | None
    hs_meeting_title: str | None
    hs_meeting_body: str | None
    hs_internal_meeting_notes: str | None
    hs_meeting_external_url: str | None
    hs_meeting_start_time: str | None
    hs_meeting_end_time: str | None
    hubspot_deal_id: str | None


def _first_contact_id_from_meeting_row(row: dict[str, Any]) -> str | None:
    assoc = row.get("associations")
    if not isinstance(assoc, dict):
        return None
    contacts = assoc.get("contacts")
    if not isinstance(contacts, dict):
        return None
    results = contacts.get("results")
    if not isinstance(results, list) or not results:
        return None
    first = results[0]
    if not isinstance(first, dict):
        return None
    cid = first.get("id")
    return _s(cid)


def list_meetings_with_contact_details(hubspot: HubSpotClient) -> list[dict[str, str | None]]:
    rows: list[tuple[str, dict[str, str | None]]] = []
    after: str | None = MEETING_LIST_INITIAL_AFTER

    for _ in range(MAX_MEETING_LIST_PAGES):
        page = hubspot.list_meetings_page(after=after, archived=False, limit=LIST_MEETINGS_PAGE_LIMIT)
        for item in page.get("results") or []:
            if not isinstance(item, dict):
                continue
            contact_id = _first_contact_id_from_meeting_row(item)
            if not contact_id:
                continue
            props = item.get("properties") if isinstance(item.get("properties"), dict) else {}
            rows.append(
                (
                    contact_id,
                    {
                        "hs_meeting_title": _s(props.get("hs_meeting_title")),
                        "hs_meeting_body": _s(props.get("hs_meeting_body")),
                        "hs_internal_meeting_notes": _s(props.get("hs_internal_meeting_notes")),
                        "hs_meeting_external_url": _s(props.get("hs_meeting_external_url")),
                        "hs_meeting_start_time": _s(props.get("hs_meeting_start_time")),
                        "hs_meeting_end_time": _s(props.get("hs_meeting_end_time")),
                    },
                )
            )

        paging = page.get("paging") if isinstance(page.get("paging"), dict) else {}
        next_page = paging.get("next") if isinstance(paging.get("next"), dict) else {}
        if next_page and not _s(next_page.get("link")):
            raise ValueError("HubSpot devolvió paging.next sin link en listado de meetings.")
        after_next = _s(next_page.get("after"))
        if not after_next:
            break
        after = after_next
    else:
        raise ValueError(f"Demasiadas páginas de meetings (>{MAX_MEETING_LIST_PAGES}).")

    contact_cache: dict[str, dict[str, Any]] = {}
    for contact_id in dict.fromkeys(c for c, _ in rows):
        contact_cache[contact_id] = hubspot.get_contact_with_associations(
            contact_id,
            associations=("deals", "deal"),
            properties=CONTACT_PROPERTIES_FOR_MEETING_LIST,
        )

    out: list[dict[str, str | None]] = []
    for contact_id, meeting_data in rows:
        c = contact_cache.get(contact_id) or {}
        cp = c.get("properties") if isinstance(c.get("properties"), dict) else {}
        deal_id = _first_deal_id_from_contact_payload(c)
        out.append(
            {
                "firstname": _s(cp.get("firstname")),
                "lastname": _s(cp.get("lastname")),
                "hs_meeting_title": meeting_data["hs_meeting_title"],
                "hs_meeting_body": meeting_data["hs_meeting_body"],
                "hs_internal_meeting_notes": meeting_data["hs_internal_meeting_notes"],
                "hs_meeting_external_url": meeting_data["hs_meeting_external_url"],
                "hs_meeting_start_time": meeting_data["hs_meeting_start_time"],
                "hs_meeting_end_time": meeting_data["hs_meeting_end_time"],
                "hubspot_deal_id": deal_id,
            }
        )
    return out

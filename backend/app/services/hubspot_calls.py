from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from app.integrations.hubspot.client import LIST_CALLS_PAGE_LIMIT, HubSpotClient
from app.integrations.hubspot.constants import CONTACT_PROPERTIES_FOR_CALL_LIST


MAX_CALL_LIST_PAGES = 500


def _s_prop(v: Any) -> str | None:
    if v is None:
        return None
    t = str(v).strip()
    return t if t else None


def _first_contact_id_from_call_row(row: dict[str, Any]) -> str | None:
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
    if cid is None or str(cid).strip() == "":
        return None
    return str(cid).strip()


def _ensure_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def hubspot_contact_datetime_string(dt: datetime) -> str:
    """Valor típico para propiedades datetime en contactos (UTC ISO)."""
    u = _ensure_utc(dt)
    return u.strftime("%Y-%m-%dT%H:%M:%S.000Z")


def hubspot_call_timestamp_ms(dt: datetime) -> str:
    """hs_timestamp en llamadas: milisegundos Unix como string."""
    u = _ensure_utc(dt)
    return str(int(u.timestamp() * 1000))


@dataclass
class CreateHubSpotCallLinkedResult:
    call_id: str
    hs_body_preview: str | None
    hs_call_title: str | None
    hs_call_to_number: str | None
    hs_call_from_number: str | None
    hs_timestamp: str | None
    hubspot_contact_id: str


def create_call_link_contact(
    client: HubSpotClient,
    *,
    crm_contact_id: str,
    to_number: str,
    from_number: str,
    title: str,
    body: str,
    call_start_time: datetime,
    call_end_time: datetime,
    association_type_id: int,
) -> CreateHubSpotCallLinkedResult:
    """
    Crea la llamada, localiza el contacto por `crm_contact_id`, actualiza tiempos en el contacto
    y asocia la llamada al contacto HubSpot.
    """
    created = client.create_call(
        properties={
            "hs_timestamp": hubspot_call_timestamp_ms(call_start_time),
            "hs_call_title": title,
            "hs_call_body": body,
            "hs_call_to_number": to_number,
            "hs_call_from_number": from_number,
        }
    )
    call_id = str(created.get("id", "")).strip()
    if not call_id:
        raise ValueError("HubSpot no devolvió id de llamada")

    props = created.get("properties") or {}
    if isinstance(props, dict):
        hs_body_preview = props.get("hs_body_preview")
        hs_call_title = props.get("hs_call_title")
        hs_call_to_number = props.get("hs_call_to_number")
        hs_call_from_number = props.get("hs_call_from_number")
        hs_timestamp = props.get("hs_timestamp")
    else:
        hs_body_preview = hs_call_title = hs_call_to_number = hs_call_from_number = hs_timestamp = None

    search = client.search_contacts_by_property_eq(
        property_name="crm_contact_id",
        value=crm_contact_id.strip(),
        limit=3,
        properties=("crm_contact_id", "call_start_time", "call_end_time"),
    )
    results = search.get("results") or []
    if not results:
        raise LookupError(
            f"No hay contacto en HubSpot con crm_contact_id={crm_contact_id!r}. "
            f"Llamada ya creada en HubSpot con id={call_id}."
        )

    hubspot_contact_id = str(results[0].get("id", "")).strip()
    if not hubspot_contact_id:
        raise LookupError(f"Resultado de búsqueda sin id para crm_contact_id={crm_contact_id!r}.")

    client.patch_contact_properties(
        hubspot_contact_id,
        {
            "call_start_time": hubspot_contact_datetime_string(call_start_time),
            "call_end_time": hubspot_contact_datetime_string(call_end_time),
        },
    )

    client.associate_call_with_contact(
        call_id=call_id,
        contact_id=hubspot_contact_id,
        association_type_id=association_type_id,
    )

    preview_str = hs_body_preview if isinstance(hs_body_preview, str) else None
    title_str = hs_call_title if isinstance(hs_call_title, str) else None
    to_str = hs_call_to_number if isinstance(hs_call_to_number, str) else None
    from_str = hs_call_from_number if isinstance(hs_call_from_number, str) else None
    ts_str = hs_timestamp if isinstance(hs_timestamp, str) else None

    return CreateHubSpotCallLinkedResult(
        call_id=call_id,
        hs_body_preview=preview_str,
        hs_call_title=title_str,
        hs_call_to_number=to_str,
        hs_call_from_number=from_str,
        hs_timestamp=ts_str,
        hubspot_contact_id=hubspot_contact_id,
    )


def list_calls_with_contact_details(client: HubSpotClient) -> list[dict[str, Any]]:
    """
    Lista todas las llamadas (paginación 100), conserva solo las que tienen asociación a contacto,
    y enriquece con propiedades del contacto HubSpot.
    """
    rows_order: list[tuple[str, dict[str, str | None]]] = []
    after: str | None = None

    for _ in range(MAX_CALL_LIST_PAGES):
        page = client.list_calls_page(
            after=after,
            archived=False,
            limit=LIST_CALLS_PAGE_LIMIT,
        )
        for item in page.get("results") or []:
            if not isinstance(item, dict):
                continue
            cid = _first_contact_id_from_call_row(item)
            if not cid:
                continue
            props = item.get("properties") if isinstance(item.get("properties"), dict) else {}
            rows_order.append(
                (
                    cid,
                    {
                        "title": _s_prop(props.get("hs_call_title")),
                        "description": _s_prop(props.get("hs_call_body")),
                        "to_number": _s_prop(props.get("hs_call_to_number")),
                        "from_number": _s_prop(props.get("hs_call_from_number")),
                    },
                )
            )

        paging = page.get("paging") if isinstance(page.get("paging"), dict) else {}
        next_page = paging.get("next") if isinstance(paging.get("next"), dict) else {}
        after = next_page.get("after")
        if after is None or str(after).strip() == "":
            break
        after = str(after).strip()
    else:
        raise ValueError(
            f"Demasiadas páginas de llamadas (>{MAX_CALL_LIST_PAGES}); se aborta por seguridad."
        )

    cache: dict[str, dict[str, Any]] = {}
    for uid in dict.fromkeys(c_id for c_id, _ in rows_order):
        cache[uid] = client.get_contact_record(uid, properties=CONTACT_PROPERTIES_FOR_CALL_LIST)

    out: list[dict[str, Any]] = []
    for cid, call_part in rows_order:
        raw = cache.get(cid) or {}
        cprops = raw.get("properties") if isinstance(raw.get("properties"), dict) else {}
        out.append(
            {
                "firstname": _s_prop(cprops.get("firstname")),
                "lastname": _s_prop(cprops.get("lastname")),
                "to_number": call_part["to_number"],
                "from_number": call_part["from_number"],
                "title": call_part["title"],
                "description": call_part["description"],
                "call_start_time": _s_prop(cprops.get("call_start_time")),
                "call_end_time": _s_prop(cprops.get("call_end_time")),
                "estatus_llamada": _s_prop(cprops.get("estatus_llamada")),
            }
        )
    return out

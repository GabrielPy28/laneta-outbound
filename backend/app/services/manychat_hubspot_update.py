from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.integrations.hubspot.client import HubSpotClient
from app.integrations.manychat.client import ManychatClient
from app.services.manychat_hubspot_sync import sync_manychat_contact_to_hubspot


@dataclass
class ManychatHubSpotContactResolution:
    id_contact: str
    manychat_id: str | None = None
    hubspot_contact_id: str | None = None
    data: dict[str, Any] = field(default_factory=dict)
    synced_contact: bool = False
    errors: list[str] = field(default_factory=list)


def _s(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def normalize_name(value: str | None) -> str:
    if not value:
        return ""
    return value.strip().lower().replace("_", " ")


def extract_manychat_field(data: dict[str, Any], *, name: str, key: str = "value") -> str | None:
    custom_fields = data.get("custom_fields")
    if not isinstance(custom_fields, list):
        return None
    target = normalize_name(name)
    for field in custom_fields:
        if not isinstance(field, dict):
            continue
        field_name = normalize_name(_s(field.get("name")))
        if field_name != target:
            continue
        return _s(field.get(key))
    return None


def resolve_manychat_hubspot_contact(
    *,
    id_contact: str,
    manychat: ManychatClient,
    hubspot: HubSpotClient,
) -> ManychatHubSpotContactResolution:
    result = ManychatHubSpotContactResolution(id_contact=str(id_contact).strip())
    payload = manychat.get_subscriber_info(result.id_contact)
    data = payload.get("data") or {}
    result.data = data if isinstance(data, dict) else {}
    result.manychat_id = _s(result.data.get("id"))
    if not result.manychat_id:
        result.errors.append("Manychat no retornó `id` del subscriber.")
        return result

    search = hubspot.search_contacts_by_property_eq(
        property_name="id_manychat",
        value=result.manychat_id,
        limit=1,
        properties=("id_manychat",),
    )
    results = search.get("results") or []
    hubspot_contact_id = _s(results[0].get("id")) if results else None
    if hubspot_contact_id:
        result.hubspot_contact_id = hubspot_contact_id
        return result

    sync_result = sync_manychat_contact_to_hubspot(
        id_contact=result.id_contact,
        manychat=manychat,
        hubspot=hubspot,
    )
    result.synced_contact = sync_result.hubspot_updated
    result.errors.extend(sync_result.errors)
    result.hubspot_contact_id = sync_result.hubspot_contact_id
    return result

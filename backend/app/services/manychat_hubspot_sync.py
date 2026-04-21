from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime
from difflib import SequenceMatcher
from typing import Any

from app.integrations.hubspot.client import HubSpotClient, HubSpotClientError
from app.integrations.manychat.client import ManychatClient, ManychatClientError


@dataclass
class ManychatHubSpotSyncResult:
    id_contact: str
    manychat_id: str | None = None
    hubspot_contact_id: str | None = None
    candidates_scanned: int = 0
    matched_by: str | None = None
    hubspot_updated: bool = False
    manychat_updated: bool = False
    errors: list[str] = field(default_factory=list)


def _s(v: Any) -> str | None:
    if v is None:
        return None
    t = str(v).strip()
    return t or None


def _normalize_text(v: str | None) -> str:
    if not v:
        return ""
    text = unicodedata.normalize("NFD", v)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    text = re.sub(r"[^a-zA-Z0-9\s]", " ", text).lower()
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _tokens(v: str | None) -> set[str]:
    t = _normalize_text(v)
    return {x for x in t.split(" ") if x}


def _normalize_phone(v: str | None) -> str:
    if not v:
        return ""
    return re.sub(r"\D", "", v)


def _phone_score(manychat_phone: str | None, hubspot_phone: str | None) -> int:
    a = _normalize_phone(manychat_phone)
    b = _normalize_phone(hubspot_phone)
    if not a or not b:
        return 0
    if a == b:
        return 120
    if len(a) >= 8 and len(b) >= 8 and (a.endswith(b[-8:]) or b.endswith(a[-8:])):
        return 90
    return 0


def _lastname_score(manychat_last_name: str | None, hubspot_last_name: str | None) -> int:
    a = _normalize_text(manychat_last_name)
    b = _normalize_text(hubspot_last_name)
    if not a or not b:
        return 0
    if a == b:
        return 100
    ta = _tokens(a)
    tb = _tokens(b)
    if ta and tb and (ta.issubset(tb) or tb.issubset(ta)):
        return 85
    inter = len(ta.intersection(tb))
    if inter > 0:
        return 55 + min(inter * 10, 20)
    ratio = SequenceMatcher(None, a, b).ratio()
    return int(ratio * 50)


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        candidate = value.replace("Z", "+00:00")
        return datetime.fromisoformat(candidate)
    except ValueError:
        return None


def _format_subscription_date(value: str | None) -> str | None:
    dt = _parse_dt(value)
    if dt is None:
        return None
    # HubSpot datetime properties expect unix epoch in milliseconds (long).
    return str(int(dt.timestamp() * 1000))


def _get_manychat_hubspot_id(custom_fields: Any) -> str | None:
    if not isinstance(custom_fields, list):
        return None
    for field in custom_fields:
        if not isinstance(field, dict):
            continue
        name = _normalize_text(_s(field.get("name")))
        if name != "hubspot id":
            continue
        value = _s(field.get("value"))
        if value:
            return value
    return None


def _choose_best_candidate(
    candidates: list[dict[str, Any]],
    *,
    manychat_last_name: str | None,
    manychat_phone: str | None,
) -> tuple[dict[str, Any] | None, str | None]:
    if not candidates:
        return None, None

    scored: list[tuple[int, datetime | None, dict[str, Any], str]] = []
    for c in candidates:
        props = c.get("properties") or {}
        phone_points = _phone_score(manychat_phone, _s(props.get("phone")))
        lastname_points = _lastname_score(manychat_last_name, _s(props.get("lastname")))
        total = phone_points + lastname_points
        reason = "phone" if phone_points >= lastname_points and phone_points > 0 else "lastname"
        scored.append((total, _parse_dt(_s(props.get("lastmodifieddate"))), c, reason))

    scored.sort(key=lambda x: (x[0], x[1] or datetime.min), reverse=True)
    top_score, _, top_candidate, reason = scored[0]
    if top_score <= 0:
        return None, None
    return top_candidate, reason


def sync_manychat_contact_to_hubspot(
    *,
    id_contact: str,
    manychat: ManychatClient,
    hubspot: HubSpotClient,
) -> ManychatHubSpotSyncResult:
    result = ManychatHubSpotSyncResult(id_contact=str(id_contact).strip())

    try:
        payload = manychat.get_subscriber_info(result.id_contact)
    except ManychatClientError as exc:
        result.errors.append(f"Manychat getInfo error: {exc}")
        return result

    data = payload.get("data") or {}
    manychat_id = _s(data.get("id"))
    first_name = _s(data.get("first_name"))
    last_name = _s(data.get("last_name"))
    whatsapp_phone = _s(data.get("whatsapp_phone"))
    manychat_hubspot_id = _get_manychat_hubspot_id(data.get("custom_fields"))
    result.manychat_id = manychat_id

    if not manychat_id:
        result.errors.append("Manychat no retornó `id` del subscriber.")
        return result
    matched_by: str | None = None
    if manychat_hubspot_id:
        hubspot_id = manychat_hubspot_id
        matched_by = "manychat_custom_field"
    else:
        if not first_name:
            result.errors.append("Manychat no retornó `first_name`, no se puede buscar en HubSpot.")
            return result

        all_candidates: list[dict[str, Any]] = []
        after: str | None = None
        while True:
            try:
                response = hubspot.search_contacts_by_firstname(first_name=first_name, limit=100, after=after)
            except HubSpotClientError as exc:
                result.errors.append(f"HubSpot firstname search error: {exc}")
                return result
            page_candidates = response.get("results") or []
            all_candidates.extend(page_candidates)
            paging = (response.get("paging") or {}).get("next") or {}
            after = _s(paging.get("after"))
            if not after:
                break

        result.candidates_scanned = len(all_candidates)
        best_candidate, matched_by = _choose_best_candidate(
            all_candidates,
            manychat_last_name=last_name,
            manychat_phone=whatsapp_phone,
        )
        if best_candidate is None:
            result.errors.append("No se pudo identificar un contacto confiable en HubSpot.")
            return result

        hubspot_id = _s(best_candidate.get("id"))
        if not hubspot_id:
            result.errors.append("El candidato seleccionado de HubSpot no tiene `id`.")
            return result

    update_properties = {
        "id_manychat": manychat_id,
        "whatsapp_chat_url": _s(data.get("live_chat_url")) or "",
        "last_whatsapp_message": _s(data.get("last_input_text")) or "",
    }
    subscribed_formatted = _format_subscription_date(_s(data.get("subscribed")))
    if subscribed_formatted:
        update_properties["whatsapp_chat_subscription_date"] = subscribed_formatted

    try:
        hubspot.patch_contact_properties(hubspot_id, update_properties)
        result.hubspot_updated = True
        result.hubspot_contact_id = hubspot_id
        result.matched_by = matched_by
    except HubSpotClientError as exc:
        result.errors.append(f"HubSpot patch error: {exc}")
        return result

    try:
        manychat.set_custom_field_by_name(
            subscriber_id=manychat_id,
            field_name="hubspot_id",
            field_value=hubspot_id,
        )
        result.manychat_updated = True
    except ManychatClientError as exc:
        result.errors.append(f"Manychat set custom field error: {exc}")

    return result

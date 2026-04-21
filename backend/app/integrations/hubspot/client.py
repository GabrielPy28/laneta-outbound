from __future__ import annotations

from typing import Any

import httpx

from app.integrations.hubspot.constants import CONTACT_SEARCH_PROPERTIES

# Fijas: no se construyen desde variables de entorno.
HUBSPOT_CRM_CONTACTS_SEARCH_URL = "https://api.hubapi.com/crm/objects/2026-03/contacts/search"
HUBSPOT_CRM_CONTACTS_RECORD_BASE_URL = "https://api.hubapi.com/crm/objects/2026-03/contacts"
HUBSPOT_CRM_DEALS_RECORD_BASE_URL = "https://api.hubapi.com/crm/objects/2026-03/deals"

DEFAULT_SEARCH_LIMIT = 14
MAX_SEARCH_LIMIT = 100


class HubSpotClientError(Exception):
    def __init__(self, message: str, *, status_code: int | None = None, body: str | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.body = body


def _format_hubspot_error_detail(status_code: int, text: str | None, *, request_url: str) -> str:
    if not text:
        return f"url={request_url}"
    t = text.lstrip()
    if t.startswith("<!DOCTYPE") or t.startswith("<html"):
        return (
            f"url={request_url} — HubSpot devolvió HTML ({status_code}), no JSON de API "
            "(revisa red, token y que el endpoint siga siendo el de CRM 2026-03)."
        )
    return f"url={request_url} — {(text or '')[:800]}"


class HubSpotClient:
    """Cliente HubSpot CRM 2026-03: búsqueda y PATCH de contactos (URLs fijas en código)."""

    def __init__(
        self,
        *,
        access_token: str,
        timeout_seconds: float = 30.0,
    ) -> None:
        self._token = access_token.strip()
        self._timeout = timeout_seconds

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def search_contacts_is_new_lead(
        self,
        *,
        limit: int = DEFAULT_SEARCH_LIMIT,
        after: str | int | None = None,
    ) -> dict[str, Any]:
        """POST contacts/search — is_new_lead EQ true (misma forma que el curl de referencia)."""
        url = HUBSPOT_CRM_CONTACTS_SEARCH_URL
        lim = min(max(int(limit), 1), MAX_SEARCH_LIMIT)
        after_str = "0" if after is None else str(after).strip() or "0"

        body: dict[str, Any] = {
            "after": after_str,
            "filterGroups": [
                {
                    "filters": [
                        {
                            "operator": "EQ",
                            "propertyName": "is_new_lead",
                            "value": "true",
                        }
                    ]
                }
            ],
            "limit": lim,
            "properties": list(CONTACT_SEARCH_PROPERTIES),
            "sorts": ["createdAt"],
        }

        with httpx.Client(timeout=self._timeout) as client:
            response = client.post(url, headers=self._headers(), json=body)

        if response.status_code >= 400:
            detail = _format_hubspot_error_detail(
                response.status_code,
                response.text,
                request_url=url,
            )
            raise HubSpotClientError(
                f"HubSpot search failed: {response.status_code} — {detail}",
                status_code=response.status_code,
                body=response.text,
            )
        return response.json()

    def search_contacts_by_firstname(
        self,
        *,
        first_name: str,
        limit: int = MAX_SEARCH_LIMIT,
        after: str | int | None = None,
    ) -> dict[str, Any]:
        """POST contacts/search filtrando por firstname EQ."""
        url = HUBSPOT_CRM_CONTACTS_SEARCH_URL
        lim = min(max(int(limit), 1), MAX_SEARCH_LIMIT)
        after_str = "0" if after is None else str(after).strip() or "0"
        body: dict[str, Any] = {
            "after": after_str,
            "filterGroups": [
                {
                    "filters": [
                        {
                            "operator": "EQ",
                            "propertyName": "firstname",
                            "value": str(first_name).strip(),
                        }
                    ]
                }
            ],
            "limit": lim,
            "properties": ["lastname", "firstname", "email", "phone", "lastmodifieddate", "createdate"],
        }
        with httpx.Client(timeout=self._timeout) as client:
            response = client.post(url, headers=self._headers(), json=body)

        if response.status_code >= 400:
            detail = _format_hubspot_error_detail(
                response.status_code,
                response.text,
                request_url=url,
            )
            raise HubSpotClientError(
                f"HubSpot firstname search failed: {response.status_code} — {detail}",
                status_code=response.status_code,
                body=response.text,
            )
        return response.json()

    def patch_contact_properties(self, contact_id: str, properties: dict[str, str]) -> dict[str, Any]:
        url = f"{HUBSPOT_CRM_CONTACTS_RECORD_BASE_URL}/{contact_id}"
        payload = {"properties": properties}

        with httpx.Client(timeout=self._timeout) as client:
            response = client.patch(url, headers=self._headers(), json=payload)

        if response.status_code >= 400:
            detail = _format_hubspot_error_detail(
                response.status_code,
                response.text,
                request_url=url,
            )
            raise HubSpotClientError(
                f"HubSpot patch contact failed: {response.status_code} — {detail}",
                status_code=response.status_code,
                body=response.text,
            )
        return response.json() if response.content else {}

    def get_contact_with_associations(
        self,
        contact_id: str,
        *,
        associations: tuple[str, ...] = ("deal",),
        properties: tuple[str, ...] = ("firstname", "email"),
    ) -> dict[str, Any]:
        """GET contacto + asociaciones. En este portal el parámetro correcto es `associations=deal`."""
        url = f"{HUBSPOT_CRM_CONTACTS_RECORD_BASE_URL}/{contact_id}"
        params: list[tuple[str, str]] = []
        for a in associations:
            params.append(("associations", a))
        for p in properties:
            params.append(("properties", p))

        with httpx.Client(timeout=self._timeout) as client:
            response = client.get(url, headers=self._headers(), params=params)

        if response.status_code >= 400:
            detail = _format_hubspot_error_detail(
                response.status_code,
                response.text,
                request_url=url,
            )
            raise HubSpotClientError(
                f"HubSpot get contact failed: {response.status_code} — {detail}",
                status_code=response.status_code,
                body=response.text,
            )
        return response.json()

    def patch_deal_properties(self, deal_id: str, properties: dict[str, str]) -> dict[str, Any]:
        url = f"{HUBSPOT_CRM_DEALS_RECORD_BASE_URL}/{deal_id}"
        payload = {"properties": properties}

        with httpx.Client(timeout=self._timeout) as client:
            response = client.patch(url, headers=self._headers(), json=payload)

        if response.status_code >= 400:
            detail = _format_hubspot_error_detail(
                response.status_code,
                response.text,
                request_url=url,
            )
            raise HubSpotClientError(
                f"HubSpot patch deal failed: {response.status_code} — {detail}",
                status_code=response.status_code,
                body=response.text,
            )
        return response.json() if response.content else {}

    def mark_contact_ingested(self, contact_id: str, supabase_lead_id: str) -> dict[str, Any]:
        """Tras guardar el lead en DB: desactiva is_new_lead y envía el id interno a HubSpot."""
        return self.patch_contact_properties(
            contact_id,
            {
                "is_new_lead": "false",
                "external_lead_id": supabase_lead_id,
            },
        )

from __future__ import annotations

from typing import Any

import httpx

from app.integrations.smartlead.constants import SMARTLEAD_API_V1_BASE


class SmartleadClientError(Exception):
    def __init__(self, message: str, *, status_code: int | None = None, body: str | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.body = body


def _format_error(status_code: int, text: str | None, *, request_url: str) -> str:
    if not text:
        return f"url={request_url}"
    t = text.lstrip()
    if len(t) > 800:
        t = t[:800] + "…"
    return f"url={request_url} — {t}"


class SmartleadClient:
    """Cliente Smartlead API v1 (`api_key` en query)."""

    def __init__(
        self,
        *,
        api_key: str,
        timeout_seconds: float = 60.0,
    ) -> None:
        self._api_key = api_key.strip()
        self._timeout = timeout_seconds

    def _params(self, **extra: str | int) -> dict[str, str | int]:
        p: dict[str, str | int] = {"api_key": self._api_key}
        p.update(extra)
        return p

    def post_campaign_leads(self, campaign_id: str, body: dict[str, Any]) -> dict[str, Any]:
        url = f"{SMARTLEAD_API_V1_BASE}/campaigns/{campaign_id}/leads"
        with httpx.Client(timeout=self._timeout) as http:
            response = http.post(url, params=self._params(), json=body)

        if response.status_code >= 400:
            detail = _format_error(response.status_code, response.text, request_url=url)
            raise SmartleadClientError(
                f"Smartlead POST leads failed: {response.status_code} — {detail}",
                status_code=response.status_code,
                body=response.text,
            )
        return response.json() if response.content else {}

    def get_lead_by_email(self, email: str) -> dict[str, Any] | None:
        """GET /leads/?email=... — 404 o sin cuerpo útil → None."""
        url = f"{SMARTLEAD_API_V1_BASE}/leads/"
        with httpx.Client(timeout=self._timeout) as http:
            response = http.get(url, params=self._params(email=email.strip()))

        if response.status_code == 404:
            return None
        if response.status_code >= 400:
            detail = _format_error(response.status_code, response.text, request_url=url)
            raise SmartleadClientError(
                f"Smartlead GET lead by email failed: {response.status_code} — {detail}",
                status_code=response.status_code,
                body=response.text,
            )
        if not response.content:
            return None
        data = response.json()
        return data if isinstance(data, dict) else None

    def get_lead_message_history(self, campaign_id: str, lead_id: str) -> dict[str, Any]:
        url = f"{SMARTLEAD_API_V1_BASE}/campaigns/{campaign_id}/leads/{lead_id}/message-history"
        with httpx.Client(timeout=self._timeout) as http:
            response = http.get(url, params=self._params())

        if response.status_code >= 400:
            detail = _format_error(response.status_code, response.text, request_url=url)
            raise SmartleadClientError(
                f"Smartlead GET message-history failed: {response.status_code} — {detail}",
                status_code=response.status_code,
                body=response.text,
            )
        return response.json() if response.content else {}

    def pause_campaign_lead(self, campaign_id: str, lead_id: str) -> dict[str, Any]:
        url = f"{SMARTLEAD_API_V1_BASE}/campaigns/{campaign_id}/leads/{lead_id}/pause"
        with httpx.Client(timeout=self._timeout) as http:
            response = http.post(url, params=self._params())

        if response.status_code >= 400:
            detail = _format_error(response.status_code, response.text, request_url=url)
            raise SmartleadClientError(
                f"Smartlead POST pause lead failed: {response.status_code} — {detail}",
                status_code=response.status_code,
                body=response.text,
            )
        return response.json() if response.content else {}

    def post_manual_complete_campaign_lead(self, campaign_id: str, campaign_lead_map_id: str) -> dict[str, Any]:
        """POST .../campaigns/{id}/leads/{campaign_lead_map_id}/manual-complete — id de mapa del export CSV."""
        mid = str(campaign_lead_map_id).strip()
        url = f"{SMARTLEAD_API_V1_BASE}/campaigns/{campaign_id}/leads/{mid}/manual-complete"
        with httpx.Client(timeout=self._timeout) as http:
            response = http.post(url, params=self._params())

        if response.status_code >= 400:
            detail = _format_error(response.status_code, response.text, request_url=url)
            raise SmartleadClientError(
                f"Smartlead POST manual-complete failed: {response.status_code} — {detail}",
                status_code=response.status_code,
                body=response.text,
            )
        return response.json() if response.content else {}

    def get_campaign_leads_export_csv(self, campaign_id: str, *, timeout_seconds: float | None = None) -> bytes:
        """GET /campaigns/{id}/leads-export — cuerpo CSV (binario)."""
        url = f"{SMARTLEAD_API_V1_BASE}/campaigns/{campaign_id}/leads-export"
        timeout = self._timeout if timeout_seconds is None else float(timeout_seconds)
        with httpx.Client(timeout=timeout) as http:
            response = http.get(url, params=self._params())

        if response.status_code >= 400:
            detail = _format_error(response.status_code, response.text, request_url=url)
            raise SmartleadClientError(
                f"Smartlead GET leads-export failed: {response.status_code} — {detail}",
                status_code=response.status_code,
                body=response.text,
            )
        return response.content or b""

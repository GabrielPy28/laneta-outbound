from __future__ import annotations

from typing import Any

import httpx

MANYCHAT_SUBSCRIBER_INFO_URL = "https://api.manychat.com/fb/subscriber/getInfo"
MANYCHAT_SET_CUSTOM_FIELD_URL = "https://api.manychat.com/fb/subscriber/setCustomFieldByName"


class ManychatClientError(Exception):
    def __init__(self, message: str, *, status_code: int | None = None, body: str | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.body = body


class ManychatClient:
    def __init__(self, *, api_key: str, timeout_seconds: float = 30.0) -> None:
        self._api_key = api_key.strip()
        self._timeout = timeout_seconds

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    def get_subscriber_info(self, subscriber_id: str) -> dict[str, Any]:
        params = {"subscriber_id": str(subscriber_id).strip()}
        with httpx.Client(timeout=self._timeout) as client:
            response = client.get(MANYCHAT_SUBSCRIBER_INFO_URL, headers=self._headers(), params=params)
        if response.status_code >= 400:
            raise ManychatClientError(
                f"Manychat getInfo failed: {response.status_code}",
                status_code=response.status_code,
                body=response.text,
            )
        payload = response.json()
        if payload.get("status") != "success":
            raise ManychatClientError(f"Manychat getInfo error: {payload}")
        return payload

    def set_custom_field_by_name(self, *, subscriber_id: str, field_name: str, field_value: str) -> dict[str, Any]:
        body = {
            "subscriber_id": str(subscriber_id).strip(),
            "field_name": field_name,
            "field_value": str(field_value),
        }
        with httpx.Client(timeout=self._timeout) as client:
            response = client.post(MANYCHAT_SET_CUSTOM_FIELD_URL, headers=self._headers(), json=body)
        if response.status_code >= 400:
            raise ManychatClientError(
                f"Manychat setCustomFieldByName failed: {response.status_code}",
                status_code=response.status_code,
                body=response.text,
            )
        payload = response.json() if response.content else {"status": "success"}
        if payload.get("status") != "success":
            raise ManychatClientError(f"Manychat setCustomFieldByName error: {payload}")
        return payload

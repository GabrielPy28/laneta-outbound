from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.hubspot.router import (
    get_hubspot_client,
    get_manychat_client,
    router as hubspot_router,
)


class FakeManychatClient:
    def get_subscriber_info(self, subscriber_id: str):
        return {
            "status": "success",
            "data": {
                "id": subscriber_id,
                "first_name": "Dayana",
                "last_name": "Vizcaya",
                "live_chat_url": "https://app.manychat.com/fb3029478/chat/1606671242",
                "last_input_text": "Crear contenidos",
                "subscribed": "2026-04-20T16:29:59-06:00",
                "whatsapp_phone": "+584122075555",
            },
        }

    def set_custom_field_by_name(self, *, subscriber_id: str, field_name: str, field_value: str):
        return {"status": "success"}


class FakeHubSpotClient:
    def search_contacts_by_firstname(self, *, first_name: str, limit: int = 100, after=None):
        return {
            "results": [
                {
                    "id": "214435535971",
                    "properties": {
                        "firstname": first_name,
                        "lastname": "Vizcaya",
                        "phone": "+584122075555",
                    },
                }
            ]
        }

    def patch_contact_properties(self, contact_id: str, properties: dict[str, str]):
        return {"id": contact_id}


def test_post_sync_manychat_contact_returns_success_payload():
    app = FastAPI()
    app.include_router(hubspot_router, prefix="/api/v1/hubspot")
    app.dependency_overrides[get_hubspot_client] = lambda: FakeHubSpotClient()
    app.dependency_overrides[get_manychat_client] = lambda: FakeManychatClient()

    with TestClient(app) as client:
        response = client.post("/api/v1/hubspot/sync-manychat-contact/1606671242")

    assert response.status_code == 200
    body = response.json()
    assert body["id_contact"] == "1606671242"
    assert body["hubspot_contact_id"] == "214435535971"
    assert body["hubspot_updated"] is True
    assert body["manychat_updated"] is True

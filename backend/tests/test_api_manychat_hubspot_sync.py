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
    def __init__(self):
        self.patch_calls = []
        self.sync_search_results = [
            {
                "id": "214435535971",
                "properties": {
                    "firstname": "Dayana",
                    "lastname": "Vizcaya",
                    "phone": "+584122075555",
                },
            }
        ]
        self.id_manychat_results = []

    def search_contacts_by_firstname(self, *, first_name: str, limit: int = 100, after=None):
        return {"results": self.sync_search_results}

    def search_contacts_by_property_eq(self, *, property_name: str, value: str, limit: int = 5, properties=None, after=None):
        return {"results": self.id_manychat_results}

    def patch_contact_properties(self, contact_id: str, properties: dict[str, str]):
        self.patch_calls.append((contact_id, properties))
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


def test_post_update_tags_crm_when_contact_exists():
    app = FastAPI()
    app.include_router(hubspot_router, prefix="/api/v1/hubspot")
    fake_hubspot = FakeHubSpotClient()
    fake_hubspot.id_manychat_results = [{"id": "214435535971"}]

    class FakeManychatClientWithFields(FakeManychatClient):
        def get_subscriber_info(self, subscriber_id: str):
            return {
                "status": "success",
                "data": {
                    "id": subscriber_id,
                    "custom_fields": [
                        {
                            "name": "tag_crm",
                            "description": "identifiers, keywords",
                            "value": "ignore-this-value",
                        },
                        {
                            "name": "Contactar con Equipo",
                            "description": "campo bandera",
                            "value": "true",
                        },
                    ],
                },
            }

    app.dependency_overrides[get_hubspot_client] = lambda: fake_hubspot
    app.dependency_overrides[get_manychat_client] = lambda: FakeManychatClientWithFields()

    with TestClient(app) as client:
        response = client.post("/api/v1/hubspot/update-tags-crm/meta_ft_lead/1606671242")

    assert response.status_code == 200
    body = response.json()
    assert body["synced_contact"] is False
    assert body["hubspot_contact_id"] == "214435535971"
    assert body["tags_crm_value"] == "identifiers, keywords"
    assert body["contactar_con_equipo_value"] == "true"
    assert body["hubspot_updated"] is True
    assert fake_hubspot.patch_calls[0][1]["tags_crm"] == "identifiers, keywords"
    assert fake_hubspot.patch_calls[0][1]["contactar_con_equipo"] == "true"


def test_post_update_tags_crm_syncs_when_contact_missing():
    app = FastAPI()
    app.include_router(hubspot_router, prefix="/api/v1/hubspot")
    fake_hubspot = FakeHubSpotClient()
    fake_hubspot.id_manychat_results = []

    class FakeManychatClientWithFields(FakeManychatClient):
        def get_subscriber_info(self, subscriber_id: str):
            return {
                "status": "success",
                "data": {
                    "id": subscriber_id,
                    "first_name": "Dayana",
                    "last_name": "Vizcaya",
                    "whatsapp_phone": "+584122075555",
                    "custom_fields": [
                        {
                            "name": "tag_crm",
                            "description": "desc for tags",
                            "value": "youtube_growth_lead",
                        }
                    ],
                },
            }

    app.dependency_overrides[get_hubspot_client] = lambda: fake_hubspot
    app.dependency_overrides[get_manychat_client] = lambda: FakeManychatClientWithFields()

    with TestClient(app) as client:
        response = client.post("/api/v1/hubspot/update-tags-crm/meta_ft_lead/1606671242")

    assert response.status_code == 200
    body = response.json()
    assert body["synced_contact"] is True
    assert body["hubspot_contact_id"] == "214435535971"
    assert body["hubspot_updated"] is True
    assert fake_hubspot.patch_calls[-1][1]["tags_crm"] == "desc for tags"


def test_post_update_tags_crm_youtube_growth_lead_contact_true_updates_both():
    app = FastAPI()
    app.include_router(hubspot_router, prefix="/api/v1/hubspot")
    fake_hubspot = FakeHubSpotClient()
    fake_hubspot.id_manychat_results = [{"id": "214435535971"}]

    class FakeManychatClientWithFields(FakeManychatClient):
        def get_subscriber_info(self, subscriber_id: str):
            return {
                "status": "success",
                "data": {
                    "id": subscriber_id,
                    "custom_fields": [
                        {
                            "name": "tag_crm",
                            "description": "yt growth descriptor",
                            "value": "youtube_growth_lead",
                        }
                    ],
                },
            }

    app.dependency_overrides[get_hubspot_client] = lambda: fake_hubspot
    app.dependency_overrides[get_manychat_client] = lambda: FakeManychatClientWithFields()

    with TestClient(app) as client:
        response = client.post("/api/v1/hubspot/update-tags-crm/youtube_growth_lead/1606671242/true")

    assert response.status_code == 200
    body = response.json()
    assert body["hubspot_updated"] is True
    assert body["contactar_con_equipo_value"] == "true"
    assert body["tags_crm_value"] == "yt growth descriptor"
    assert fake_hubspot.patch_calls[-1][1]["contactar_con_equipo"] == "true"
    assert fake_hubspot.patch_calls[-1][1]["tags_crm"] == "yt growth descriptor"


def test_post_update_tags_crm_youtube_growth_lead_contact_false_updates_only_contactar():
    app = FastAPI()
    app.include_router(hubspot_router, prefix="/api/v1/hubspot")
    fake_hubspot = FakeHubSpotClient()
    fake_hubspot.id_manychat_results = [{"id": "214435535971"}]

    app.dependency_overrides[get_hubspot_client] = lambda: fake_hubspot
    app.dependency_overrides[get_manychat_client] = lambda: FakeManychatClient()

    with TestClient(app) as client:
        response = client.post("/api/v1/hubspot/update-tags-crm/youtube_growth_lead/1606671242/false")

    assert response.status_code == 200
    body = response.json()
    assert body["hubspot_updated"] is True
    assert body["contactar_con_equipo_value"] == "false"
    assert "tags_crm" not in fake_hubspot.patch_calls[-1][1]
    assert fake_hubspot.patch_calls[-1][1]["contactar_con_equipo"] == "false"


def test_post_support_meta_ft_lead_updates_only_contactar():
    app = FastAPI()
    app.include_router(hubspot_router, prefix="/api/v1/hubspot")
    fake_hubspot = FakeHubSpotClient()
    fake_hubspot.id_manychat_results = [{"id": "214435535971"}]

    app.dependency_overrides[get_hubspot_client] = lambda: fake_hubspot
    app.dependency_overrides[get_manychat_client] = lambda: FakeManychatClient()

    with TestClient(app) as client:
        response = client.post("/api/v1/hubspot/support/meta_ft_lead/1606671242/true")

    assert response.status_code == 200
    body = response.json()
    assert body["hubspot_updated"] is True
    assert body["contactar_con_equipo_value"] == "true"
    assert "tags_crm" not in fake_hubspot.patch_calls[-1][1]
    assert fake_hubspot.patch_calls[-1][1] == {"contactar_con_equipo": "true"}

"""POST/GET /api/v1/hubspot/calls"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.hubspot.router import get_hubspot_client, router as hubspot_router
from app.integrations.hubspot.client import HubSpotClient
from app.integrations.hubspot.constants import CONTACT_PROPERTIES_FOR_CALL_LIST


class FakeHubSpotCalls(HubSpotClient):
    """Cliente mínimo para el flujo crear llamada + contacto (sin llamar a HubSpot)."""

    def __init__(self) -> None:
        super().__init__(access_token="tok")

    def create_call(self, *, properties: dict[str, str], associations: list | None = None):  # type: ignore[override]
        self.last_create_props = properties
        return {
            "id": "108433330027",
            "properties": {
                "hs_body_preview": properties.get("hs_call_body", "")[:50],
                "hs_call_title": properties.get("hs_call_title"),
                "hs_call_to_number": properties.get("hs_call_to_number"),
                "hs_call_from_number": properties.get("hs_call_from_number"),
                "hs_timestamp": "2026-04-22T23:12:29.332Z",
            },
        }

    def search_contacts_by_property_eq(self, **kwargs):  # type: ignore[override]
        self.search_kwargs = kwargs
        return {"results": [{"id": "214435535971"}]}

    def patch_contact_properties(self, contact_id: str, properties: dict[str, str]):  # type: ignore[override]
        self.patched_contact_id = contact_id
        self.patched_props = properties
        return {"id": contact_id}

    def associate_call_with_contact(self, *, call_id: str, contact_id: str, association_type_id: int):  # type: ignore[override]
        self.assoc = (call_id, contact_id, association_type_id)
        return {"fromObjectId": int(call_id), "toObjectId": int(contact_id)}


def test_post_calls_happy_path():
    fake = FakeHubSpotCalls()
    app = FastAPI()
    app.include_router(hubspot_router, prefix="/api/v1/hubspot")
    app.dependency_overrides[get_hubspot_client] = lambda: fake

    start = datetime(2026, 4, 22, 12, 0, tzinfo=timezone.utc)
    end = datetime(2026, 4, 22, 12, 30, tzinfo=timezone.utc)

    with TestClient(app) as client:
        r = client.post(
            "/api/v1/hubspot/calls",
            json={
                "crm_contact_id": "ext-42",
                "to_number": "+584127823455",
                "from_number": "+525519641958",
                "title": "Prueba",
                "body": "Notas",
                "call_start_time": start.isoformat(),
                "call_end_time": end.isoformat(),
            },
        )

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["id"] == "108433330027"
    assert body["hubspot_contact_id"] == "214435535971"
    assert body["hs_call_title"] == "Prueba"
    assert fake.search_kwargs["property_name"] == "crm_contact_id"
    assert fake.search_kwargs["value"] == "ext-42"
    assert fake.patched_props["call_start_time"].startswith("2026-04-22")
    assert fake.assoc[0] == "108433330027"
    assert fake.assoc[1] == "214435535971"


class FakeHubSpotCallsList(HubSpotClient):
    """GET /calls — listado enriquecido."""

    def __init__(self) -> None:
        super().__init__(access_token="tok")

    def list_calls_page(
        self,
        *,
        after: str | None = None,
        archived: bool = False,
        limit: int = 100,
    ) -> dict[str, Any]:
        _ = archived, limit
        if after is not None:
            return {"results": [], "paging": {}}
        return {
            "results": [
                {
                    "id": "c1",
                    "properties": {
                        "hs_call_title": "X",
                        "hs_call_body": "Y",
                        "hs_call_to_number": "+1",
                        "hs_call_from_number": "+2",
                    },
                    "associations": {
                        "contacts": {"results": [{"id": "99"}]},
                    },
                }
            ],
            "paging": {},
        }

    def get_contact_record(
        self,
        contact_id: str,
        *,
        properties: tuple[str, ...],
    ) -> dict[str, Any]:
        assert contact_id == "99"
        assert properties == CONTACT_PROPERTIES_FOR_CALL_LIST
        return {
            "properties": {
                "firstname": "F",
                "lastname": "G",
                "call_start_time": "2026-01-01T00:00:00Z",
                "call_end_time": "2026-01-01T01:00:00Z",
                "estatus_llamada": "ok",
            }
        }


def test_get_calls_list_returns_array():
    app = FastAPI()
    app.include_router(hubspot_router, prefix="/api/v1/hubspot")
    app.dependency_overrides[get_hubspot_client] = lambda: FakeHubSpotCallsList()

    with TestClient(app) as client:
        r = client.get("/api/v1/hubspot/calls")

    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["firstname"] == "F"
    assert data[0]["title"] == "X"


def test_post_calls_validation_end_before_start():
    app = FastAPI()
    app.include_router(hubspot_router, prefix="/api/v1/hubspot")
    app.dependency_overrides[get_hubspot_client] = lambda: FakeHubSpotCalls()

    with TestClient(app) as client:
        r = client.post(
            "/api/v1/hubspot/calls",
            json={
                "crm_contact_id": "x",
                "to_number": "1",
                "from_number": "2",
                "title": "t",
                "body": "b",
                "call_start_time": "2026-04-22T14:00:00Z",
                "call_end_time": "2026-04-22T12:00:00Z",
            },
        )

    assert r.status_code == 422

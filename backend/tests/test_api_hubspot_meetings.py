"""POST /api/v1/hubspot/meetings"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.hubspot.router import get_hubspot_client, router as hubspot_router
from app.integrations.hubspot.client import HubSpotClient
from app.services.hubspot_meetings import MEETING_LIST_INITIAL_AFTER


class FakeMeetingHubSpot(HubSpotClient):
    def __init__(self) -> None:
        super().__init__(access_token="tok")

    def search_contacts_by_property_eq(self, **kwargs):  # type: ignore[override]
        assert kwargs["property_name"] == "crm_contact_id"
        return {
            "results": [
                {
                    "id": "214435535971",
                    "properties": {
                        "firstname": "Gabriel",
                        "lastname": "Piñero",
                        "email": "gabriel@laneta.com",
                    },
                }
            ]
        }

    def get_contact_with_associations(
        self,
        contact_id: str,
        *,
        associations: tuple[str, ...] = ("deal",),
        properties: tuple[str, ...] = ("firstname", "email"),
    ) -> dict[str, Any]:  # type: ignore[override]
        assert contact_id == "214435535971"
        return {
            "properties": {
                "firstname": "Gabriel",
                "lastname": "Piñero",
            },
            "associations": {
                "deals": {"results": [{"id": "59153054330"}]},
            }
        }

    def create_meeting(self, *, properties: dict[str, str], associations: list | None = None):  # type: ignore[override]
        self.last_meeting_props = properties
        return {
            "id": "108429510472",
            "properties": {
                "hs_meeting_title": properties.get("hs_meeting_title"),
                "hs_meeting_body": properties.get("hs_meeting_body"),
                "hs_internal_meeting_notes": properties.get("hs_internal_meeting_notes"),
                "hs_meeting_external_url": properties.get("hs_meeting_external_url"),
                "hs_meeting_start_time": properties.get("hs_meeting_start_time"),
                "hs_meeting_end_time": properties.get("hs_meeting_end_time"),
            },
        }

    def patch_deal_properties(self, deal_id: str, properties: dict[str, str]):  # type: ignore[override]
        self.deal_patch = (deal_id, properties)
        return {"id": deal_id}

    def associate_meeting_with_contact_default(self, *, meeting_id: str, contact_id: str):  # type: ignore[override]
        self.assoc = (meeting_id, contact_id)
        return {"status": "COMPLETE"}

    def list_meetings_page(self, *, after: str | None = None, archived: bool = False, limit: int = 100):  # type: ignore[override]
        _ = archived, limit
        if after and after != MEETING_LIST_INITIAL_AFTER:
            return {"results": [], "paging": {}}
        return {
            "results": [
                {
                    "id": "108429510472",
                    "properties": {
                        "hs_meeting_title": "Titulo",
                        "hs_meeting_body": "Body",
                        "hs_internal_meeting_notes": "Notas",
                        "hs_meeting_external_url": "https://calendar.google.com/test",
                        "hs_meeting_start_time": "2026-04-23T10:30:00Z",
                        "hs_meeting_end_time": "2026-04-23T11:00:00Z",
                    },
                    "associations": {"contacts": {"results": [{"id": "214435535971"}]}},
                }
            ],
            "paging": {},
        }


@patch("app.services.hubspot_meetings.insert_calendar_event")
def test_post_meetings_happy_path(mock_cal):
    mock_cal.return_value = {"htmlLink": "https://www.google.com/calendar/event?eid=test"}

    fake = FakeMeetingHubSpot()
    app = FastAPI()
    app.include_router(hubspot_router, prefix="/api/v1/hubspot")
    app.dependency_overrides[get_hubspot_client] = lambda: fake

    start = datetime(2026, 4, 23, 17, 30, tzinfo=timezone.utc)
    end = datetime(2026, 4, 23, 18, 0, tzinfo=timezone.utc)

    with TestClient(app) as client:
        r = client.post(
            "/api/v1/hubspot/meetings",
            json={
                "crm_contact_id": "ext-1",
                "email": "gabriel@laneta.com",
                "title": "Reunión prueba",
                "description": "Desc",
                "additional_notes": "Notas internas",
                "start_time": start.isoformat(),
                "end_time": end.isoformat(),
            },
        )

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["id"] == "108429510472"
    assert body["hubspot_contact_id"] == "214435535971"
    assert body["hubspot_deal_id"] == "59153054330"
    assert body["calendar_html_link"].startswith("https://")
    assert fake.deal_patch[1]["dealstage"] == "1340627368"
    assert fake.assoc == ("108429510472", "214435535971")
    mock_cal.assert_called_once()


@patch("app.services.hubspot_meetings.insert_calendar_event")
def test_post_meetings_without_deal_still_succeeds(mock_cal):
    mock_cal.return_value = {"htmlLink": "https://www.google.com/calendar/event?eid=test2"}

    class NoDealFake(FakeMeetingHubSpot):
        def get_contact_with_associations(self, contact_id: str, *, associations=("deal",), properties=("firstname", "email")):
            _ = contact_id, associations, properties
            return {"associations": {"deals": {"results": []}}}

        def patch_deal_properties(self, deal_id: str, properties: dict[str, str]):  # type: ignore[override]
            raise AssertionError("No debe intentar actualizar deal si no existe")

    fake = NoDealFake()
    app = FastAPI()
    app.include_router(hubspot_router, prefix="/api/v1/hubspot")
    app.dependency_overrides[get_hubspot_client] = lambda: fake

    start = datetime(2026, 4, 23, 17, 30, tzinfo=timezone.utc)
    end = datetime(2026, 4, 23, 18, 0, tzinfo=timezone.utc)

    with TestClient(app) as client:
        r = client.post(
            "/api/v1/hubspot/meetings",
            json={
                "crm_contact_id": "ext-1",
                "email": "gabriel@laneta.com",
                "title": "Reunión sin deal",
                "description": "Desc",
                "start_time": start.isoformat(),
                "end_time": end.isoformat(),
            },
        )

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["hubspot_contact_id"] == "214435535971"
    assert body["hubspot_deal_id"] is None
    assert body["calendar_html_link"].startswith("https://")
    assert fake.assoc == ("108429510472", "214435535971")


def test_get_meetings_list_returns_expected_shape():
    fake = FakeMeetingHubSpot()
    app = FastAPI()
    app.include_router(hubspot_router, prefix="/api/v1/hubspot")
    app.dependency_overrides[get_hubspot_client] = lambda: fake

    with TestClient(app) as client:
        r = client.get("/api/v1/hubspot/meetings")

    assert r.status_code == 200, r.text
    data = r.json()
    assert isinstance(data, list)
    assert len(data) == 1
    row = data[0]
    assert row["firstname"] == "Gabriel"
    assert row["lastname"] == "Piñero"
    assert row["hs_meeting_title"] == "Titulo"
    assert row["hs_meeting_external_url"].startswith("https://")
    assert row["hubspot_deal_id"] == "59153054330"

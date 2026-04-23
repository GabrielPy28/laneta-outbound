"""Servicio list_calls_with_contact_details y paginación."""

from __future__ import annotations

from typing import Any

from app.integrations.hubspot.client import HubSpotClient
from app.integrations.hubspot.constants import CONTACT_PROPERTIES_FOR_CALL_LIST
from app.services.hubspot_calls import list_calls_with_contact_details


class FakeListHubSpot(HubSpotClient):
    def __init__(self) -> None:
        super().__init__(access_token="tok")

    def list_calls_page(
        self,
        *,
        after: str | None = None,
        archived: bool = False,
        limit: int = 100,
    ) -> dict[str, Any]:
        assert archived is False
        if after is None:
            return {
                "results": [
                    {
                        "id": "noassoc",
                        "properties": {
                            "hs_call_title": "solo",
                            "hs_call_body": None,
                            "hs_call_to_number": None,
                            "hs_call_from_number": None,
                        },
                        "associations": {},
                    },
                    {
                        "id": "withassoc",
                        "properties": {
                            "hs_call_title": "T1",
                            "hs_call_body": "D1",
                            "hs_call_to_number": "+11",
                            "hs_call_from_number": "+22",
                        },
                        "associations": {
                            "contacts": {"results": [{"id": "214435535971", "type": "call_to_contact"}]}
                        },
                    },
                ],
                "paging": {"next": {"after": "nextcur"}},
            }
        if after == "nextcur":
            return {"results": [], "paging": {}}
        raise AssertionError(f"unexpected after={after!r}")

    def get_contact_record(
        self,
        contact_id: str,
        *,
        properties: tuple[str, ...],
    ) -> dict[str, Any]:
        assert contact_id == "214435535971"
        assert properties == CONTACT_PROPERTIES_FOR_CALL_LIST
        return {
            "properties": {
                "firstname": "Ann",
                "lastname": "Bee",
                "call_start_time": "2026-04-22T12:00:00.000Z",
                "call_end_time": "2026-04-22T13:00:00.000Z",
                "estatus_llamada": "done",
            }
        }


def test_list_calls_filters_and_merges_contact():
    rows = list_calls_with_contact_details(FakeListHubSpot())
    assert len(rows) == 1
    r = rows[0]
    assert r["firstname"] == "Ann"
    assert r["lastname"] == "Bee"
    assert r["title"] == "T1"
    assert r["description"] == "D1"
    assert r["to_number"] == "+11"
    assert r["from_number"] == "+22"
    assert r["call_start_time"].startswith("2026-04-22")
    assert r["estatus_llamada"] == "done"


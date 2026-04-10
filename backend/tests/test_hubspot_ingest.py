from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.integrations.hubspot.client import HubSpotClientError
from app.models.lead import Lead
from app.services import hubspot_ingest as ingest
from app.services.hubspot_ingest import sync_new_leads_from_hubspot


class FakeHubSpotClient:
    """Sustituto de HubSpotClient para pruebas (sin HTTP)."""

    def __init__(self, search_pages: list[dict[str, Any]]) -> None:
        self._pages = list(search_pages)
        self.search_calls: list[tuple[int, str | None]] = []
        self.mark_calls: list[tuple[str, str]] = []
        self.fail_mark_for: set[str] = set()

    def search_contacts_is_new_lead(self, *, limit: int = 100, after: str | None = None) -> dict[str, Any]:
        self.search_calls.append((limit, after))
        if not self._pages:
            raise RuntimeError("No hay más páginas simuladas")
        return self._pages.pop(0)

    def mark_contact_ingested(self, contact_id: str, supabase_lead_id: str) -> dict[str, Any]:
        if contact_id in self.fail_mark_for:
            raise HubSpotClientError("patch failed", status_code=500, body="err")
        self.mark_calls.append((contact_id, supabase_lead_id))
        return {}


def test_sync_creates_lead_and_marks_hubspot(sqlite_session: Session) -> None:
    fake = FakeHubSpotClient(
        [
            {
                "results": [
                    {
                        "id": "hs-1",
                        "properties": {
                            "email": "lead@example.com",
                            "firstname": "Luis",
                            "lastname": "Pérez",
                            "company": "Acme",
                            "jobtitle": "CTO",
                        },
                    }
                ],
            }
        ]
    )

    result = sync_new_leads_from_hubspot(sqlite_session, fake)

    assert result.pages_fetched == 1
    assert result.contacts_scanned == 1
    assert result.created == 1
    assert result.updated == 0
    assert result.hubspot_marked_done == 1
    assert result.hubspot_mark_failed == 0
    row = sqlite_session.scalar(select(Lead).where(Lead.email == "lead@example.com"))
    assert row is not None
    assert fake.mark_calls == [("hs-1", str(row.id))]
    assert row.external_lead_id == str(row.id)
    assert row.hubspot_contact_id == "hs-1"
    assert row.first_name == "Luis"
    assert row.engagement_status == "NEW"


def test_sync_paginates_until_no_after(sqlite_session: Session) -> None:
    fake = FakeHubSpotClient(
        [
            {
                "results": [{"id": "1", "properties": {"email": "a@a.com"}}],
                "paging": {"next": {"after": "c2"}},
            },
            {
                "results": [{"id": "2", "properties": {"email": "b@b.com"}}],
            },
        ]
    )

    result = sync_new_leads_from_hubspot(sqlite_session, fake)

    assert result.pages_fetched == 2
    assert result.created == 2
    assert len(fake.mark_calls) == 2
    assert fake.search_calls[0][1] is None
    assert fake.search_calls[1][1] == "c2"


def test_sync_skips_contact_without_email(sqlite_session: Session) -> None:
    fake = FakeHubSpotClient(
        [
            {
                "results": [
                    {"id": "x", "properties": {}},
                ],
            }
        ]
    )

    result = sync_new_leads_from_hubspot(sqlite_session, fake)
    assert result.skipped_no_email == 1
    assert result.created == 0
    assert fake.mark_calls == []


def test_sync_on_patch_failure_sets_error_flag(sqlite_session: Session) -> None:
    fake = FakeHubSpotClient(
        [
            {
                "results": [
                    {"id": "hs-bad", "properties": {"email": "bad@example.com"}},
                ],
            }
        ]
    )
    fake.fail_mark_for.add("hs-bad")

    result = sync_new_leads_from_hubspot(sqlite_session, fake)

    assert result.hubspot_mark_failed == 1
    row = sqlite_session.scalar(select(Lead).where(Lead.email == "bad@example.com"))
    assert row is not None
    assert row.error_flag is True
    assert row.error_message is not None


def test_sync_stops_on_hubspot_search_error(sqlite_session: Session) -> None:
    class BrokenSearchClient(FakeHubSpotClient):
        def search_contacts_is_new_lead(self, *, limit: int = 100, after: str | None = None) -> dict:
            raise HubSpotClientError("boom", status_code=429, body="rate")

    result = sync_new_leads_from_hubspot(sqlite_session, BrokenSearchClient([]))
    assert result.pages_fetched == 0
    assert result.errors
    assert "HubSpot search error" in result.errors[0]


def test_apply_hubspot_properties_maps_fields() -> None:
    lead = Lead(email="m@x.com", hubspot_contact_id="10")
    ingest._apply_hubspot_properties(
        lead,
        {
            "firstname": "M",
            "lastname": "N",
            "company": "Co",
            "website": "https://co.com",
            "hs_linkedin_url": "https://linkedin.com/in/m",
            "company_size": "50",
            "lead_score": "7",
            "hs_email_last_email_name": "Hola",
            "pais": "MX",
            "hs_email_last_open_date": "2026-01-15T10:00:00Z",
        },
        hubspot_id="10",
    )
    assert lead.first_name == "M"
    assert lead.company_size == 50
    assert lead.lead_score == 7
    assert "linkedin.com" in (lead.linkedin_url or "")
    assert lead.last_email_subject == "Hola"
    assert lead.country == "MX"
    assert lead.last_open_date is not None


def test_apply_prefers_nombre_ultimo_mensaje_over_hs_email_last_name() -> None:
    lead = Lead(email="x@y.com", hubspot_contact_id="1")
    ingest._apply_hubspot_properties(
        lead,
        {
            "nombre_ultimo_mensaje": "Desde custom",
            "hs_email_last_email_name": "Desde HubSpot",
        },
        hubspot_id="1",
    )
    assert lead.last_email_subject == "Desde custom"

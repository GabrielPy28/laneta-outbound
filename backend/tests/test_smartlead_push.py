from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.integrations.hubspot.client import HubSpotClientError
from app.models.lead import Lead
from app.services.smartlead_push import (
    lead_to_smartlead_lead_dict,
    push_new_leads_to_smartlead_campaign,
    resolve_smartlead_lead_id_for_campaign,
)


class FakeSmartleadClient:
    def __init__(self) -> None:
        self._next_id = 1
        self.post_calls: list[dict[str, Any]] = []
        self.email_to_id: dict[str, str] = {}

    def post_campaign_leads(self, campaign_id: str, body: dict[str, Any]) -> dict[str, Any]:
        self.post_calls.append(body)
        added = 0
        for item in body["lead_list"]:
            email = str(item["email"]).strip().lower()
            if email not in self.email_to_id:
                self.email_to_id[email] = str(self._next_id)
                self._next_id += 1
                added += 1
        return {"added_count": added, "skipped_count": len(body["lead_list"]) - added}

    def get_lead_by_email(self, email: str) -> dict[str, Any] | None:
        key = email.strip().lower()
        sid = self.email_to_id.get(key)
        if not sid:
            return None
        return {
            "id": sid,
            "email": email,
            "lead_campaign_data": [{"campaign_id": 3154960}],
        }


class FakeHubSpotClient:
    def __init__(self) -> None:
        self.patches: list[tuple[str, dict[str, str]]] = []
        self.fail_for: set[str] = set()

    def patch_contact_properties(self, contact_id: str, properties: dict[str, str]) -> dict[str, Any]:
        if contact_id in self.fail_for:
            raise HubSpotClientError("patch failed", status_code=500, body="err")
        self.patches.append((contact_id, dict(properties)))
        return {}


def test_lead_to_smartlead_maps_standard_and_custom_fields() -> None:
    lead = Lead(
        email="x@y.com",
        first_name="A",
        last_name="B",
        company_name="Co",
        website="https://co.com",
        country="MX",
        job_title="VP",
        company_size=10,
    )
    d = lead_to_smartlead_lead_dict(lead)
    assert d["email"] == "x@y.com"
    assert d["first_name"] == "A"
    assert d["company_url"] == "https://co.com"
    assert d["custom_fields"]["job_title"] == "VP"
    assert d["custom_fields"]["company_size"] == "10"


def test_resolve_smartlead_lead_id_uses_get_lead_by_email() -> None:
    fake = FakeSmartleadClient()
    fake.email_to_id["a@b.com"] = "3599381160"
    assert resolve_smartlead_lead_id_for_campaign(fake, "A@B.com", "3154960") == "3599381160"


def test_resolve_smartlead_rejects_wrong_campaign_in_lead_campaign_data() -> None:
    class FakeWithWrongCampaign:
        def get_lead_by_email(self, email: str) -> dict[str, Any]:
            return {
                "id": "1",
                "email": email,
                "lead_campaign_data": [{"campaign_id": 999}],
            }

    assert resolve_smartlead_lead_id_for_campaign(FakeWithWrongCampaign(), "x@y.com", "3154960") is None


def test_push_updates_db_and_hubspot(sqlite_session: Session) -> None:
    sqlite_session.add(
        Lead(
            email="p1@example.com",
            hubspot_contact_id="hs-1",
            first_name="P",
            engagement_status="NEW",
        )
    )
    sqlite_session.commit()

    sl = FakeSmartleadClient()
    hs = FakeHubSpotClient()
    push_new_leads_to_smartlead_campaign(sqlite_session, sl, hs, campaign_id="3154960", max_leads=50)

    row = sqlite_session.scalar(select(Lead).where(Lead.email == "p1@example.com"))
    assert row is not None
    assert row.smartlead_lead_id == "1"
    assert row.campaign_id == "3154960"
    assert row.engagement_status == "CONTACTED"
    assert row.sequence_status == "active"
    assert len(hs.patches) == 1
    assert hs.patches[0][0] == "hs-1"
    assert hs.patches[0][1]["smartlead_lead_id"] == "1"
    assert hs.patches[0][1]["engagement_status"] == "CONTACTED"
    assert hs.patches[0][1]["sequence_status"] == "ACTIVE"
    assert hs.patches[0][1]["campaign_id"] == "3154960"


def test_push_skips_hubspot_without_contact_id(sqlite_session: Session) -> None:
    sqlite_session.add(Lead(email="solo@example.com"))
    sqlite_session.commit()

    result = push_new_leads_to_smartlead_campaign(
        sqlite_session,
        FakeSmartleadClient(),
        FakeHubSpotClient(),
        campaign_id="3154960",
        max_leads=50,
    )
    assert result.hubspot_skipped_no_contact == 1
    row = sqlite_session.scalar(select(Lead).where(Lead.email == "solo@example.com"))
    assert row is not None
    assert row.smartlead_lead_id is not None

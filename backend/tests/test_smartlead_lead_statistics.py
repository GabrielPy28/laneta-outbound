from __future__ import annotations

import uuid

from sqlalchemy import select

from app.models.lead import Lead
from app.models.lead_statistics import LeadStatistics
from app.services.smartlead_lead_statistics import (
    compute_lead_score,
    derive_engagement_status,
    derive_last_event_type,
    sync_lead_statistics_from_smartlead_export,
)
class FakeHubSpotMerge:
    """Acumula PATCH por contacto (como propiedades mergeadas)."""

    def __init__(self) -> None:
        self.by_contact: dict[str, dict[str, str]] = {}

    def patch_contact_properties(self, contact_id: str, properties: dict[str, str]) -> dict:
        m = self.by_contact.setdefault(contact_id, {})
        m.update(dict(properties))
        return {}


class FakeExportSmartlead:
    def __init__(self, csv_bytes: bytes) -> None:
        self._csv = csv_bytes
        self.campaign_ids: list[str] = []
        self.manual_completes: list[tuple[str, str]] = []
        self.pauses: list[tuple[str, str]] = []

    def get_campaign_leads_export_csv(self, campaign_id: str, *, timeout_seconds: float | None = None) -> bytes:
        self.campaign_ids.append(campaign_id)
        return self._csv

    def post_manual_complete_campaign_lead(self, campaign_id: str, campaign_lead_map_id: str) -> dict:
        self.manual_completes.append((campaign_id, str(campaign_lead_map_id)))
        return {}

    def pause_campaign_lead(self, campaign_id: str, lead_id: str) -> dict:
        self.pauses.append((campaign_id, str(lead_id)))
        return {}


def test_compute_lead_score_and_last_event_priority() -> None:
    assert compute_lead_score(2, 0, 0) == 10
    assert compute_lead_score(0, 1, 0) == 10
    assert compute_lead_score(0, 0, 1) == 20
    assert compute_lead_score(1, 1, 1) == 5 + 10 + 20

    assert derive_last_event_type(1, 0, 0) == "EMAIL_OPENED"
    assert derive_last_event_type(0, 1, 0) == "LINK_CLICKED"
    assert derive_last_event_type(1, 1, 0) == "LINK_CLICKED"
    assert derive_last_event_type(0, 0, 1) == "EMAIL_REPLIED"
    assert derive_last_event_type(5, 5, 1) == "EMAIL_REPLIED"
    assert derive_last_event_type(0, 0, 0) == "EMAIL_SENT"

    assert derive_engagement_status(0, 0, 0) == "NO_OPEN"
    assert derive_engagement_status(1, 0, 0) == "OPEN_NO_CLICK"
    assert derive_engagement_status(1, 1, 0) == "CLICKED"
    assert derive_engagement_status(0, 1, 0) == "CLICKED"
    assert derive_engagement_status(0, 0, 1) == "REPLIED"
    assert derive_engagement_status(5, 5, 1) == "REPLIED"


def test_sync_lead_statistics_from_export(sqlite_session) -> None:
    cid = "3154960"
    csv_body = (
        b'"id","open_count","click_count","reply_count","last_email_sequence_sent","status","is_interested","category","campaign_lead_map_id"\n'
        b'"100","1","2","0","3","INPROGRESS","false","Interested","9001"\n'
        b'"200","0","0","1","1","PAUSED","true","Interested","9002"\n'
    )
    sl = FakeExportSmartlead(csv_body)
    hs = FakeHubSpotMerge()

    lid_a = uuid.uuid4()
    lid_b = uuid.uuid4()
    sqlite_session.add_all(
        [
            Lead(
                id=lid_a,
                email="a@sameorg.test",
                smartlead_lead_id="100",
                campaign_id=cid,
                hubspot_contact_id="hs-a",
            ),
            Lead(
                id=lid_b,
                email="b@sameorg.test",
                smartlead_lead_id="200",
                campaign_id=cid,
                hubspot_contact_id="hs-b",
            ),
        ]
    )
    sqlite_session.commit()

    r = sync_lead_statistics_from_smartlead_export(sqlite_session, sl, hs, campaign_id=cid)
    assert r.export_rows == 2
    assert r.matched_leads == 2
    assert r.statistics_upserted == 2
    assert r.hubspot_patched == 3
    assert not r.errors

    sa = sqlite_session.get(LeadStatistics, lid_a)
    assert sa is not None
    assert sa.total_opens == 1 and sa.total_clicks == 2 and sa.total_replies == 0
    assert sa.lead_score == 5 + 20
    assert sa.last_event_type == "LINK_CLICKED"
    assert sa.last_sequence_step == "3"

    sb = sqlite_session.get(LeadStatistics, lid_b)
    assert sb is not None
    assert sb.total_replies == 1
    assert sb.lead_score == 20
    assert sb.last_event_type == "EMAIL_REPLIED"

    row_a = sqlite_session.get(Lead, lid_a)
    assert row_a is not None
    assert row_a.total_clicks == 2
    assert row_a.lead_score == 25
    assert row_a.engagement_status == "CLICKED"
    assert row_a.reply_type == "Interested"
    assert row_a.is_qualified is False
    assert row_a.sequence_status == "completed"

    row_b = sqlite_session.get(Lead, lid_b)
    assert row_b is not None
    assert row_b.engagement_status == "REPLIED"
    assert row_b.reply_type == "Interested"
    assert row_b.is_qualified is True
    assert row_b.sequence_status == "completed"

    assert len(sl.manual_completes) == 2
    assert set(sl.manual_completes) == {(cid, "9001"), (cid, "9002")}

    by_hs = hs.by_contact
    assert by_hs["hs-a"]["total_opens"] == "1"
    assert by_hs["hs-a"]["total_clicks"] == "2"
    assert by_hs["hs-a"]["lead_score"] == "0.25"
    assert by_hs["hs-a"]["last_sequence_step"] == "3"
    assert by_hs["hs-a"]["last_event_type"] == "LINK_CLICKED"
    assert by_hs["hs-a"]["engagement_status"] == "CLICKED"
    assert by_hs["hs-a"]["reply_type"] == "INTERESTED"
    assert by_hs["hs-a"]["is_qualified"] == "false"
    assert by_hs["hs-a"]["sequence_status"] == "COMPLETED"

    assert by_hs["hs-b"]["last_event_type"] == "EMAIL_REPLIED"
    assert by_hs["hs-b"]["engagement_status"] == "REPLIED"
    assert by_hs["hs-b"]["reply_type"] == "INTERESTED"
    assert by_hs["hs-b"]["is_qualified"] == "true"
    assert by_hs["hs-b"]["sequence_status"] == "COMPLETED"


def test_sync_skips_wrong_campaign(sqlite_session) -> None:
    csv_body = (
        b'"id","open_count","click_count","reply_count","last_email_sequence_sent","status","is_interested","category","campaign_lead_map_id"\n'
        b'"50","9","0","0","1","INPROGRESS","false","","5050"\n'
    )
    sl = FakeExportSmartlead(csv_body)
    lid = uuid.uuid4()
    sqlite_session.add(
        Lead(
            id=lid,
            email="x@example.com",
            smartlead_lead_id="50",
            campaign_id="other",
            hubspot_contact_id="hs-x",
        )
    )
    sqlite_session.commit()

    r = sync_lead_statistics_from_smartlead_export(sqlite_session, sl, None, campaign_id="3154960")
    assert r.matched_leads == 0
    assert r.statistics_upserted == 0
    assert sqlite_session.scalar(select(LeadStatistics).where(LeadStatistics.id_lead == lid)) is None


def test_sync_pause_not_interested_only_one_lead(sqlite_session) -> None:
    cid = "3154960"
    csv_body = (
        b'"id","open_count","click_count","reply_count","last_email_sequence_sent","status","is_interested","category","campaign_lead_map_id"\n'
        b'"300","0","0","1","1","INPROGRESS","false","Not Interested","9300"\n'
    )
    sl = FakeExportSmartlead(csv_body)
    lid = uuid.uuid4()
    sqlite_session.add(
        Lead(
            id=lid,
            email="solo@company.test",
            smartlead_lead_id="300",
            campaign_id=cid,
            hubspot_contact_id=None,
        )
    )
    sqlite_session.commit()

    r = sync_lead_statistics_from_smartlead_export(sqlite_session, sl, None, campaign_id=cid)
    assert not r.errors
    assert sl.pauses == [(cid, "300")]
    assert sl.manual_completes == []
    row = sqlite_session.get(Lead, lid)
    assert row is not None
    assert row.sequence_status == "paused"

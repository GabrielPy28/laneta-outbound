from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.deps import get_hubspot_client_optional
from app.db.session import get_session
from app.api.smartlead.router import get_smartlead_client, router as smartlead_router
from app.api.smartlead.schemas import (
    SmartleadLeadStatisticsSyncResponse,
    SmartleadPushCampaignResponse,
)


def _build_app(sqlite_session, fake_sl, fake_hs=None):
    app = FastAPI()
    app.include_router(smartlead_router, prefix="/api/v1/smartlead")

    def _session():
        yield sqlite_session

    def _sl():
        return fake_sl

    def _hs():
        return fake_hs

    app.dependency_overrides[get_session] = _session
    app.dependency_overrides[get_smartlead_client] = _sl
    app.dependency_overrides[get_hubspot_client_optional] = _hs
    return app


def test_post_push_returns_schema(sqlite_session):
    from app.models.lead import Lead
    from tests.test_smartlead_push import FakeHubSpotClient, FakeSmartleadClient

    sqlite_session.add(Lead(email="api@x.com"))
    sqlite_session.commit()

    app = _build_app(sqlite_session, FakeSmartleadClient(), FakeHubSpotClient())
    with TestClient(app) as client:
        r = client.post("/api/v1/smartlead/push-campaign-leads")

    assert r.status_code == 200
    body = r.json()
    SmartleadPushCampaignResponse.model_validate(body)
    assert body["leads_selected"] == 1
    assert body["hubspot_available"] is True


def test_post_sync_campaign_lead_statistics_returns_schema(sqlite_session):
    import uuid

    from app.models.lead import Lead
    from tests.test_smartlead_lead_statistics import FakeExportSmartlead
    from tests.test_smartlead_push import FakeHubSpotClient

    cid = "3154960"
    csv_body = (
        b'"id","open_count","click_count","reply_count","last_email_sequence_sent","status","is_interested","category","campaign_lead_map_id"\n'
        b'"77","0","0","0","1","INPROGRESS","false","","7701"\n'
    )
    sqlite_session.add(
        Lead(
            id=uuid.uuid4(),
            email="stat@x.com",
            smartlead_lead_id="77",
            campaign_id=cid,
            hubspot_contact_id="hs77",
        )
    )
    sqlite_session.commit()

    app = _build_app(sqlite_session, FakeExportSmartlead(csv_body), FakeHubSpotClient())
    with TestClient(app) as client:
        r = client.post("/api/v1/smartlead/sync-campaign-lead-statistics", params={"campaign_id": cid})

    assert r.status_code == 200
    body = r.json()
    SmartleadLeadStatisticsSyncResponse.model_validate(body)
    assert body["matched_leads"] == 1
    assert body["statistics_upserted"] == 1


def test_push_without_hubspot_token_still_ok(sqlite_session):
    from tests.test_smartlead_push import FakeSmartleadClient

    from app.models.lead import Lead

    sqlite_session.add(Lead(email="nohs@x.com", hubspot_contact_id="x"))
    sqlite_session.commit()

    app = _build_app(sqlite_session, FakeSmartleadClient(), None)
    with TestClient(app) as client:
        r = client.post("/api/v1/smartlead/push-campaign-leads")

    assert r.status_code == 200
    assert r.json()["hubspot_available"] is False
    assert r.json()["hubspot_patched"] == 0

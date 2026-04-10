from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.leads.router import router as leads_router
from app.core.config import get_settings
from app.core.jwt_utils import create_access_token
from app.db.session import get_session
from app.models.lead import Lead
from app.models.lead_message_history import LeadMessageHistory
from app.models.lead_statistics import LeadStatistics


def _mini_app(sqlite_session):
    app = FastAPI()
    app.include_router(leads_router, prefix="/api/v1/leads")

    def _session():
        yield sqlite_session

    app.dependency_overrides[get_session] = _session
    return app


def test_activity_404(monkeypatch: pytest.MonkeyPatch, sqlite_session):
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@localhost:5432/db")
    monkeypatch.setenv("JWT_SECRET_KEY", "act-secret")
    get_settings.cache_clear()
    token = create_access_token(sub="u1", email="a@b.com", name="T")
    app = _mini_app(sqlite_session)
    with TestClient(app) as client:
        r = client.get(
            f"/api/v1/leads/{uuid.uuid4()}/activity",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert r.status_code == 404


def test_activity_200(monkeypatch: pytest.MonkeyPatch, sqlite_session):
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@localhost:5432/db")
    monkeypatch.setenv("JWT_SECRET_KEY", "act-secret")
    get_settings.cache_clear()

    lid = uuid.uuid4()
    sqlite_session.add(
        Lead(
            id=lid,
            email="x@y.com",
            first_name="Ada",
            last_name="Lovelace",
        )
    )
    sqlite_session.add(
        LeadStatistics(
            id_lead=lid,
            campaign_id="c1",
            total_opens=2,
            total_clicks=1,
            total_replies=0,
            lead_score=10,
        )
    )
    ts = datetime.now(timezone.utc)
    sqlite_session.add(
        LeadMessageHistory(
            lead_id=lid,
            message_id="mid-1",
            direction="outbound",
            subject="Hola",
            sent_at=ts,
            email_body="<p>Hola</p>",
        )
    )
    sqlite_session.commit()

    token = create_access_token(sub="u1", email="a@b.com", name="T")
    app = _mini_app(sqlite_session)
    with TestClient(app) as client:
        r = client.get(
            f"/api/v1/leads/{lid}/activity",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert r.status_code == 200
    body = r.json()
    assert body["lead"]["display_name"] == "Ada Lovelace"
    assert body["statistics"]["total_opens"] == 2
    assert len(body["messages"]) == 1
    assert body["messages"][0]["direction"] == "outbound"

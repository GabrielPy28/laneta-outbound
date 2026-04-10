from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.campaign_active.router import router as campaign_active_router
from app.core.config import get_settings
from app.core.jwt_utils import create_access_token
from app.db.session import get_session
from app.integrations.smartlead.constants import SMARTLEAD_DEFAULT_CAMPAIGN_ID
def _mini_app(sqlite_session):
    app = FastAPI()
    app.include_router(campaign_active_router, prefix="/api/v1/campaign-active")

    def _session():
        yield sqlite_session

    app.dependency_overrides[get_session] = _session
    return app


def test_campaign_active_get_default(monkeypatch: pytest.MonkeyPatch, sqlite_session):
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@localhost:5432/db")
    monkeypatch.setenv("JWT_SECRET_KEY", "camp-test-secret")
    get_settings.cache_clear()
    token = create_access_token(sub="u1", email="a@b.com", name="T")

    app = _mini_app(sqlite_session)
    with TestClient(app) as client:
        r = client.get(
            "/api/v1/campaign-active",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert r.status_code == 200
    body = r.json()
    assert body["active"] is None
    assert body["effective_id_campaign"] == SMARTLEAD_DEFAULT_CAMPAIGN_ID


def test_campaign_active_put_then_get(monkeypatch: pytest.MonkeyPatch, sqlite_session):
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@localhost:5432/db")
    monkeypatch.setenv("JWT_SECRET_KEY", "camp-test-secret")
    get_settings.cache_clear()
    token = create_access_token(sub="u1", email="a@b.com", name="T")

    app = _mini_app(sqlite_session)
    with TestClient(app) as client:
        r_put = client.put(
            "/api/v1/campaign-active",
            headers={"Authorization": f"Bearer {token}"},
            json={"id_campaign": "9998888"},
        )
        assert r_put.status_code == 200
        assert r_put.json()["effective_id_campaign"] == "9998888"

        r_get = client.get(
            "/api/v1/campaign-active",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert r_get.status_code == 200
    assert r_get.json()["active"]["id_campaign"] == "9998888"
    assert r_get.json()["active"]["status"] == "Active"


def test_campaign_active_401(sqlite_session):
    app = _mini_app(sqlite_session)
    with TestClient(app) as client:
        r = client.get("/api/v1/campaign-active")
    assert r.status_code == 401

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.leads.router import router as leads_router
from app.core.config import get_settings
from app.core.jwt_utils import create_access_token
from app.db.session import get_session
from app.models.lead import Lead


def _mini_app(sqlite_session):
    app = FastAPI()
    app.include_router(leads_router, prefix="/api/v1/leads")

    def _session():
        yield sqlite_session

    app.dependency_overrides[get_session] = _session
    return app


def test_leads_401_without_token(sqlite_session):
    app = _mini_app(sqlite_session)
    with TestClient(app) as client:
        r = client.get("/api/v1/leads")
    assert r.status_code == 401


def test_leads_200_with_valid_jwt(monkeypatch: pytest.MonkeyPatch, sqlite_session):
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@localhost:5432/db")
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-leads")
    get_settings.cache_clear()

    sqlite_session.add(
        Lead(
            email="lead@example.com",
            first_name="Ana",
            company_name="ACME",
            sequence_status="active",
            engagement_status="engaged",
        )
    )
    sqlite_session.commit()

    token = create_access_token(sub="u1", email="a@b.com", name="Tester")
    app = _mini_app(sqlite_session)
    with TestClient(app) as client:
        r = client.get(
            "/api/v1/leads",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 1
    assert len(body["items"]) == 1
    assert body["items"][0]["email"] == "lead@example.com"
    assert body["items"][0]["first_name"] == "Ana"


def test_leads_limit_must_be_allowed(monkeypatch: pytest.MonkeyPatch, sqlite_session):
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@localhost:5432/db")
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-leads")
    get_settings.cache_clear()
    token = create_access_token(sub="u1", email="a@b.com", name="Tester")
    app = _mini_app(sqlite_session)
    with TestClient(app) as client:
        r = client.get(
            "/api/v1/leads?limit=99",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert r.status_code == 400


def test_leads_filter_email(monkeypatch: pytest.MonkeyPatch, sqlite_session):
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@localhost:5432/db")
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-leads")
    get_settings.cache_clear()

    sqlite_session.add_all(
        [
            Lead(email="a@x.com", first_name="A"),
            Lead(email="b@unique.com", first_name="B"),
        ]
    )
    sqlite_session.commit()

    token = create_access_token(sub="u1", email="a@b.com", name="Tester")
    app = _mini_app(sqlite_session)
    with TestClient(app) as client:
        r = client.get(
            "/api/v1/leads",
            headers={"Authorization": f"Bearer {token}"},
            params={"filter_email": "unique"},
        )
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 1
    assert len(body["items"]) == 1
    assert body["items"][0]["email"] == "b@unique.com"

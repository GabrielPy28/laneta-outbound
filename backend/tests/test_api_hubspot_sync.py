"""
Pruebas del endpoint HTTP `POST /api/v1/hubspot/sync-new-leads`.

Usan una app FastAPI mínima (sin lifespan de BD global) y sustituyen las
dependencias por una sesión SQLite en memoria y un cliente HubSpot falso.

Para validar contra HubSpot real y tu Postgres, usa el servidor con `.env` y
Swagger o curl; los tests automatizados aquí no sustituyen esa comprobación manual
salvo que añadas tests de integración con credenciales (no incluidos por defecto).
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.hubspot.router import get_hubspot_client, router as hubspot_router
from app.api.hubspot.schemas import HubSpotNewLeadsSyncResponse
from app.db.session import get_session
from tests.test_hubspot_ingest import FakeHubSpotClient


def _build_app(sqlite_session, fake_hubspot: FakeHubSpotClient) -> FastAPI:
    app = FastAPI()
    app.include_router(hubspot_router, prefix="/api/v1/hubspot")

    def _override_session():
        yield sqlite_session

    def _override_hubspot():
        return fake_hubspot

    app.dependency_overrides[get_session] = _override_session
    app.dependency_overrides[get_hubspot_client] = _override_hubspot
    return app


def test_post_sync_new_leads_returns_schema_and_persists(sqlite_session):
    fake = FakeHubSpotClient(
        [
            {
                "results": [
                    {
                        "id": "hs-api-1",
                        "properties": {
                            "email": "api-test@example.com",
                            "firstname": "API",
                        },
                    }
                ],
            }
        ]
    )
    app = _build_app(sqlite_session, fake)

    with TestClient(app) as client:
        response = client.post("/api/v1/hubspot/sync-new-leads")

    assert response.status_code == 200
    body = response.json()
    parsed = HubSpotNewLeadsSyncResponse.model_validate(body)
    assert parsed.created == 1
    assert parsed.hubspot_marked_done == 1
    assert len(fake.mark_calls) == 1
    assert fake.mark_calls[0][0] == "hs-api-1"


def test_post_sync_new_leads_propagates_error_summary(sqlite_session):
    class BoomSearch(FakeHubSpotClient):
        def search_contacts_is_new_lead(self, *, limit: int = 100, after: str | None = None):
            from app.integrations.hubspot.client import HubSpotClientError

            raise HubSpotClientError("rate", status_code=429)

    app = _build_app(sqlite_session, BoomSearch([]))

    with TestClient(app) as client:
        response = client.post("/api/v1/hubspot/sync-new-leads")

    assert response.status_code == 200
    assert response.json()["errors"]

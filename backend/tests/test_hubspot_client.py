from unittest.mock import patch

import httpx
import pytest

from app.integrations.hubspot.client import (
    DEFAULT_SEARCH_LIMIT,
    HUBSPOT_CRM_CONTACTS_RECORD_BASE_URL,
    HUBSPOT_CRM_CONTACTS_SEARCH_URL,
    HubSpotClient,
    HubSpotClientError,
)
from app.integrations.hubspot.constants import CONTACT_SEARCH_PROPERTIES


def test_search_uses_static_url_and_curl_shaped_body():
    mock_response = httpx.Response(
        200,
        json={
            "results": [{"id": "123", "properties": {"email": "a@b.com", "firstname": "Ann"}}],
        },
    )

    with patch("httpx.Client") as MockClient:
        inst = MockClient.return_value.__enter__.return_value
        inst.post.return_value = mock_response
        c = HubSpotClient(access_token="tok")
        data = c.search_contacts_is_new_lead()

    assert data["results"][0]["id"] == "123"
    url = inst.post.call_args[0][0]
    assert url == HUBSPOT_CRM_CONTACTS_SEARCH_URL
    body = inst.post.call_args[1]["json"]
    assert body["after"] == "0"
    assert body["limit"] == DEFAULT_SEARCH_LIMIT
    assert body["sorts"] == ["createdAt"]
    assert body["properties"] == list(CONTACT_SEARCH_PROPERTIES)
    f0 = body["filterGroups"][0]["filters"][0]
    assert f0["operator"] == "EQ"
    assert f0["propertyName"] == "is_new_lead"
    assert f0["value"] == "true"
    assert "query" not in body


def test_search_sends_string_after_cursor():
    mock_response = httpx.Response(200, json={"results": []})

    with patch("httpx.Client") as MockClient:
        inst = MockClient.return_value.__enter__.return_value
        inst.post.return_value = mock_response
        HubSpotClient(access_token="tok").search_contacts_is_new_lead(after="2")

    assert inst.post.call_args[1]["json"]["after"] == "2"


def test_search_raises_on_http_error():
    mock_response = httpx.Response(401, text="nope")

    with patch("httpx.Client") as MockClient:
        inst = MockClient.return_value.__enter__.return_value
        inst.post.return_value = mock_response
        with pytest.raises(HubSpotClientError) as exc:
            HubSpotClient(access_token="tok").search_contacts_is_new_lead()
        assert exc.value.status_code == 401


def test_mark_contact_ingested_patch_payload():
    mock_response = httpx.Response(200, json={"id": "99"})
    internal_id = "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11"

    with patch("httpx.Client") as MockClient:
        inst = MockClient.return_value.__enter__.return_value
        inst.patch.return_value = mock_response
        HubSpotClient(access_token="tok").mark_contact_ingested("99", internal_id)

    url = inst.patch.call_args[0][0]
    assert url == f"{HUBSPOT_CRM_CONTACTS_RECORD_BASE_URL}/99"
    assert inst.patch.call_args[1]["json"] == {
        "properties": {
            "is_new_lead": "false",
            "external_lead_id": internal_id,
        }
    }

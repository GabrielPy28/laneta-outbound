from unittest.mock import patch

import httpx
import pytest

from app.integrations.hubspot.client import (
    DEFAULT_SEARCH_LIMIT,
    HUBSPOT_CRM_CALLS_BASE_URL,
    HUBSPOT_CRM_CONTACTS_RECORD_BASE_URL,
    HUBSPOT_CRM_CONTACTS_SEARCH_URL,
    HUBSPOT_CRM_MEETINGS_BASE_URL,
    HubSpotClient,
    HubSpotClientError,
    LIST_CALLS_PAGE_LIMIT,
    LIST_MEETINGS_PAGE_LIMIT,
)
from app.integrations.hubspot.constants import CALL_LIST_PROPERTY_NAMES, MEETING_LIST_PROPERTY_NAMES
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


def test_create_call_post_payload():
    mock_response = httpx.Response(
        200,
        json={
            "id": "108433330027",
            "properties": {
                "hs_call_title": "T",
                "hs_body_preview": "preview",
                "hs_timestamp": "2024-09-18T22:40:00Z",
            },
        },
    )

    with patch("httpx.Client") as MockClient:
        inst = MockClient.return_value.__enter__.return_value
        inst.post.return_value = mock_response
        HubSpotClient(access_token="tok").create_call(
            properties={
                "hs_timestamp": "1726699200000",
                "hs_call_title": "T",
                "hs_call_body": "B",
                "hs_call_to_number": "+1",
                "hs_call_from_number": "+2",
            }
        )

    url = inst.post.call_args[0][0]
    assert url == HUBSPOT_CRM_CALLS_BASE_URL
    assert inst.post.call_args[1]["json"]["properties"]["hs_call_title"] == "T"


def test_search_contacts_by_property_eq_filters():
    mock_response = httpx.Response(200, json={"results": [{"id": "214435535971"}]})

    with patch("httpx.Client") as MockClient:
        inst = MockClient.return_value.__enter__.return_value
        inst.post.return_value = mock_response
        HubSpotClient(access_token="tok").search_contacts_by_property_eq(
            property_name="crm_contact_id",
            value="abc-123",
            limit=3,
            properties=("crm_contact_id",),
        )

    body = inst.post.call_args[1]["json"]
    assert body["filterGroups"][0]["filters"][0]["propertyName"] == "crm_contact_id"
    assert body["filterGroups"][0]["filters"][0]["value"] == "abc-123"


def test_associate_call_with_contact_put_url():
    mock_response = httpx.Response(200, json={"fromObjectId": 1})

    with patch("httpx.Client") as MockClient:
        inst = MockClient.return_value.__enter__.return_value
        inst.put.return_value = mock_response
        HubSpotClient(access_token="tok").associate_call_with_contact(
            call_id="108433330027",
            contact_id="214435535971",
            association_type_id=194,
        )

    url = inst.put.call_args[0][0]
    assert (
        url
        == f"{HUBSPOT_CRM_CALLS_BASE_URL}/108433330027/associations/contact/214435535971/194"
    )


def test_list_calls_page_get_params():
    mock_response = httpx.Response(200, json={"results": [], "paging": {}})
    with patch("httpx.Client") as MockClient:
        inst = MockClient.return_value.__enter__.return_value
        inst.get.return_value = mock_response
        HubSpotClient(access_token="tok").list_calls_page(after="3608294621")

    kwargs = inst.get.call_args
    assert kwargs[0][0] == HUBSPOT_CRM_CALLS_BASE_URL
    params = kwargs[1]["params"]
    assert ("limit", str(LIST_CALLS_PAGE_LIMIT)) in params
    assert ("associations", "contacts") in params
    assert ("archived", "false") in params
    assert ("after", "3608294621") in params
    for p in CALL_LIST_PROPERTY_NAMES:
        assert ("properties", p) in params


def test_get_contact_record_properties_only():
    mock_response = httpx.Response(
        200,
        json={"id": "99", "properties": {"firstname": "A"}},
    )
    with patch("httpx.Client") as MockClient:
        inst = MockClient.return_value.__enter__.return_value
        inst.get.return_value = mock_response
        HubSpotClient(access_token="tok").get_contact_record(
            "99",
            properties=("firstname", "lastname"),
        )

    url = inst.get.call_args[0][0]
    assert url == f"{HUBSPOT_CRM_CONTACTS_RECORD_BASE_URL}/99"
    params = inst.get.call_args[1]["params"]
    assert params.count(("properties", "firstname")) == 1
    assert params.count(("properties", "lastname")) == 1


def test_create_meeting_posts_to_meetings_url():
    mock_response = httpx.Response(200, json={"id": "m1", "properties": {}})
    with patch("httpx.Client") as MockClient:
        inst = MockClient.return_value.__enter__.return_value
        inst.post.return_value = mock_response
        HubSpotClient(access_token="tok").create_meeting(
            properties={"hs_meeting_title": "T"},
        )
    assert inst.post.call_args[0][0] == HUBSPOT_CRM_MEETINGS_BASE_URL


def test_associate_meeting_default_put_no_json_body():
    mock_response = httpx.Response(200, json={"status": "COMPLETE"})
    with patch("httpx.Client") as MockClient:
        inst = MockClient.return_value.__enter__.return_value
        inst.put.return_value = mock_response
        HubSpotClient(access_token="tok").associate_meeting_with_contact_default(
            meeting_id="108429510472",
            contact_id="214435535971",
        )
    url = inst.put.call_args[0][0]
    assert url == (
        f"{HUBSPOT_CRM_MEETINGS_BASE_URL}/108429510472"
        "/associations/default/contact/214435535971"
    )
    assert "json" not in inst.put.call_args[1]


def test_list_meetings_page_get_params():
    mock_response = httpx.Response(200, json={"results": [], "paging": {}})
    with patch("httpx.Client") as MockClient:
        inst = MockClient.return_value.__enter__.return_value
        inst.get.return_value = mock_response
        HubSpotClient(access_token="tok").list_meetings_page(after="91652235822")

    kwargs = inst.get.call_args
    assert kwargs[0][0] == HUBSPOT_CRM_MEETINGS_BASE_URL
    params = kwargs[1]["params"]
    assert ("limit", str(LIST_MEETINGS_PAGE_LIMIT)) in params
    assert ("associations", "contacts") in params
    assert ("archived", "false") in params
    assert ("after", "91652235822") in params
    for p in MEETING_LIST_PROPERTY_NAMES:
        assert ("properties", p) in params

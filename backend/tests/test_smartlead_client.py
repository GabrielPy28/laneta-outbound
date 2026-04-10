from unittest.mock import patch

import httpx
import pytest

from app.integrations.smartlead.client import SmartleadClient, SmartleadClientError
from app.integrations.smartlead.constants import SMARTLEAD_API_V1_BASE


def test_post_campaign_leads_sends_api_key_query():
    mock_response = httpx.Response(200, json={"added_count": 1, "skipped_count": 0})

    with patch("httpx.Client") as MockClient:
        inst = MockClient.return_value.__enter__.return_value
        inst.post.return_value = mock_response
        SmartleadClient(api_key=" k ").post_campaign_leads(
            "3154960",
            {"lead_list": [{"email": "a@b.com"}], "settings": {}},
        )

    inst.post.assert_called_once()
    url = inst.post.call_args[0][0]
    assert url == f"{SMARTLEAD_API_V1_BASE}/campaigns/3154960/leads"
    params = inst.post.call_args[1]["params"]
    assert params["api_key"] == "k"


def test_get_lead_by_email_query():
    mock_response = httpx.Response(200, json={"id": "3599381160", "email": "mery@laneta.com"})

    with patch("httpx.Client") as MockClient:
        inst = MockClient.return_value.__enter__.return_value
        inst.get.return_value = mock_response
        out = SmartleadClient(api_key="x").get_lead_by_email("mery@laneta.com")

    assert out is not None
    assert out["id"] == "3599381160"
    inst.get.assert_called_once()
    url = inst.get.call_args[0][0]
    assert url == f"{SMARTLEAD_API_V1_BASE}/leads/"
    params = inst.get.call_args[1]["params"]
    assert params["api_key"] == "x"
    assert params["email"] == "mery@laneta.com"


def test_get_lead_by_email_404_returns_none():
    mock_response = httpx.Response(404, text="not found")

    with patch("httpx.Client") as MockClient:
        inst = MockClient.return_value.__enter__.return_value
        inst.get.return_value = mock_response
        out = SmartleadClient(api_key="x").get_lead_by_email("missing@x.com")

    assert out is None


def test_get_lead_message_history_url():
    mock_response = httpx.Response(200, json={"messages": []})

    with patch("httpx.Client") as MockClient:
        inst = MockClient.return_value.__enter__.return_value
        inst.get.return_value = mock_response
        SmartleadClient(api_key="k").get_lead_message_history("3154960", "789")

    url = inst.get.call_args[0][0]
    assert url == f"{SMARTLEAD_API_V1_BASE}/campaigns/3154960/leads/789/message-history"


def test_get_campaign_leads_export_url():
    mock_response = httpx.Response(200, content=b'"id","open_count"\n')

    with patch("httpx.Client") as MockClient:
        inst = MockClient.return_value.__enter__.return_value
        inst.get.return_value = mock_response
        out = SmartleadClient(api_key="k").get_campaign_leads_export_csv("3154960")

    assert out == b'"id","open_count"\n'
    url = inst.get.call_args[0][0]
    assert url == f"{SMARTLEAD_API_V1_BASE}/campaigns/3154960/leads-export"
    params = inst.get.call_args[1]["params"]
    assert params["api_key"] == "k"


def test_post_manual_complete_campaign_lead_url():
    mock_response = httpx.Response(200, json={"ok": True})

    with patch("httpx.Client") as MockClient:
        inst = MockClient.return_value.__enter__.return_value
        inst.post.return_value = mock_response
        SmartleadClient(api_key="k").post_manual_complete_campaign_lead("3154960", "2929720212")

    url = inst.post.call_args[0][0]
    assert url == f"{SMARTLEAD_API_V1_BASE}/campaigns/3154960/leads/2929720212/manual-complete"
    assert inst.post.call_args[1]["params"]["api_key"] == "k"


def test_pause_campaign_lead_posts():
    mock_response = httpx.Response(200, json={"ok": True})

    with patch("httpx.Client") as MockClient:
        inst = MockClient.return_value.__enter__.return_value
        inst.post.return_value = mock_response
        SmartleadClient(api_key="k").pause_campaign_lead("1", "2")

    url = inst.post.call_args[0][0]
    assert url == f"{SMARTLEAD_API_V1_BASE}/campaigns/1/leads/2/pause"


def test_post_raises_smartlead_client_error():
    mock_response = httpx.Response(401, text="nope")

    with patch("httpx.Client") as MockClient:
        inst = MockClient.return_value.__enter__.return_value
        inst.post.return_value = mock_response
        with pytest.raises(SmartleadClientError) as exc:
            SmartleadClient(api_key="x").post_campaign_leads("1", {"lead_list": []})
    assert exc.value.status_code == 401

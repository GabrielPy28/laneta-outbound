from __future__ import annotations

from app.services.manychat_hubspot_sync import sync_manychat_contact_to_hubspot


class FakeManychatClient:
    def __init__(self, payload):
        self.payload = payload
        self.custom_field_calls = []

    def get_subscriber_info(self, subscriber_id: str):
        return self.payload

    def set_custom_field_by_name(self, *, subscriber_id: str, field_name: str, field_value: str):
        self.custom_field_calls.append((subscriber_id, field_name, field_value))
        return {"status": "success"}


class FakeHubSpotClient:
    def __init__(self, pages):
        self.pages = pages
        self.patch_calls = []
        self.search_calls = 0

    def search_contacts_by_firstname(self, *, first_name: str, limit: int = 100, after=None):
        self.search_calls += 1
        if after in (None, "0"):
            return self.pages[0]
        if after == "next-1":
            return self.pages[1]
        return {"results": []}

    def patch_contact_properties(self, contact_id: str, properties: dict[str, str]):
        self.patch_calls.append((contact_id, properties))
        return {"id": contact_id}


def test_sync_manychat_to_hubspot_uses_phone_as_tiebreaker():
    manychat_payload = {
        "status": "success",
        "data": {
            "id": "1606671242",
            "first_name": "Gabriel",
            "last_name": "Pinero Wong Ferres",
            "live_chat_url": "https://app.manychat.com/chat/1606671242",
            "last_input_text": "Crear contenidos",
            "subscribed": "2026-04-20T16:29:59-06:00",
            "whatsapp_phone": "+1 (905) 530-2500",
        },
    }
    hubspot = FakeHubSpotClient(
        [
            {
                "results": [
                    {
                        "id": "135315801",
                        "properties": {
                            "firstname": "Gabriel",
                            "lastname": "Del Huerto",
                            "phone": "+5491158061536",
                        },
                    },
                    {
                        "id": "214435535971",
                        "properties": {
                            "firstname": "Gabriel",
                            "lastname": "Wong",
                            "phone": "+1 (905) 530-2500",
                        },
                    },
                ]
            }
        ]
    )
    manychat = FakeManychatClient(manychat_payload)

    result = sync_manychat_contact_to_hubspot(
        id_contact="1606671242",
        manychat=manychat,
        hubspot=hubspot,
    )

    assert result.hubspot_contact_id == "214435535971"
    assert result.matched_by == "phone"
    assert result.hubspot_updated is True
    assert result.manychat_updated is True
    assert len(hubspot.patch_calls) == 1
    _, patched = hubspot.patch_calls[0]
    assert patched["id_manychat"] == "1606671242"
    assert patched["whatsapp_chat_url"] == "https://app.manychat.com/chat/1606671242"
    assert patched["last_whatsapp_message"] == "Crear contenidos"
    assert patched["whatsapp_chat_subscription_date"] == "1776724199000"
    assert manychat.custom_field_calls[0] == ("1606671242", "hubspot_id", "214435535971")


def test_sync_manychat_to_hubspot_returns_error_when_no_confident_match():
    manychat = FakeManychatClient(
        {
            "status": "success",
            "data": {
                "id": "1",
                "first_name": "Gabriel",
                "last_name": "Pinero",
                "whatsapp_phone": None,
            },
        }
    )
    hubspot = FakeHubSpotClient(
        [
            {
                "results": [
                    {
                        "id": "A",
                        "properties": {"firstname": "Gabriel", "lastname": None, "phone": None},
                    }
                ]
            }
        ]
    )

    result = sync_manychat_contact_to_hubspot(id_contact="1", manychat=manychat, hubspot=hubspot)
    assert result.hubspot_updated is False
    assert result.errors


def test_sync_manychat_to_hubspot_uses_custom_field_hubspot_id_first():
    manychat = FakeManychatClient(
        {
            "status": "success",
            "data": {
                "id": "241842626",
                "first_name": "Gabriel",
                "last_name": "Pinero",
                "live_chat_url": "https://app.manychat.com/fb3029478/chat/241842626",
                "last_input_text": "Hablar con un asesor",
                "subscribed": "2026-04-21T11:10:27-06:00",
                "whatsapp_phone": "+584127823455",
                "custom_fields": [
                    {
                        "id": 14509894,
                        "name": "hubspot_id",
                        "type": "text",
                        "value": "214435535971",
                    }
                ],
            },
        }
    )
    hubspot = FakeHubSpotClient([{"results": []}])

    result = sync_manychat_contact_to_hubspot(id_contact="241842626", manychat=manychat, hubspot=hubspot)

    assert result.hubspot_contact_id == "214435535971"
    assert result.matched_by == "manychat_custom_field"
    assert result.hubspot_updated is True
    assert hubspot.search_calls == 0

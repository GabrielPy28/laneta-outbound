from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.lead import Lead
from app.models.lead_message_history import LeadMessageHistory
from app.services.smartlead_message_history import sync_smartlead_message_history_for_lead


class FakeSmartleadMsgClient:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload
        self.paused: list[tuple[str, str]] = []

    def get_lead_message_history(self, campaign_id: str, lead_id: str) -> dict[str, Any]:
        return self.payload

    def pause_campaign_lead(self, campaign_id: str, lead_id: str) -> dict[str, Any]:
        self.paused.append((campaign_id, lead_id))
        return {}


class FakeHubSpot:
    def __init__(self) -> None:
        self.last_props: dict[str, str] | None = None

    def patch_contact_properties(self, contact_id: str, properties: dict[str, str]) -> dict[str, Any]:
        self.last_props = dict(properties)
        return {}


def _sample_history() -> dict[str, Any]:
    """Forma real Smartlead: `history` con type SENT | REPLY y `message_id` / `time`."""
    return {
        "from": "brands@partners.lanetahub.com",
        "to": "one@acme.test",
        "history": [
            {
                "stats_id": "9d0d083e-3e9c-4d94-a307-3cfbb6310023",
                "from": "brands@partners.lanetahub.com",
                "to": "one@acme.test",
                "type": "SENT",
                "message_id": "<m1@partners.lanetahub.com>",
                "time": "2025-01-15T10:00:00.000Z",
                "subject": "Hello",
                "email_body": "<p>Hi</p>",
                "email_seq_number": "1",
                "open_count": 1,
                "click_count": 0,
            },
            {
                "stats_id": "9d0d083e-3e9c-4d94-a307-3cfbb6310023",
                "from": "one@acme.test",
                "to": "brands@partners.lanetahub.com",
                "type": "REPLY",
                "message_id": "<m2@gmail.com>",
                "time": "2025-01-20T14:00:00.000Z",
                "email_body": (
                    '<div dir="auto">I am interested. Let\'s talk.</div><br>'
                    '<div class="gmail_quote gmail_quote_container">'
                    "<div>Older thread from brands</div></div>"
                ),
                "email_seq_number": "1",
                "cc": [],
            },
        ],
    }


def _sample_messages_legacy() -> dict[str, Any]:
    """Formato antiguo (`messages`) sigue soportado."""
    return {
        "messages": [
            {
                "id": "m1",
                "subject": "Hello",
                "direction": "outbound",
                "sent_at": "2025-01-15T10:00:00Z",
                "opened_at": "2025-01-15T10:30:00Z",
                "email_body": "<p>Hi</p>",
            },
            {
                "id": "m2",
                "subject": "Re: Hello",
                "direction": "inbound",
                "received_at": "2025-01-20T14:00:00Z",
                "email_body": "<html>I am interested. Let's talk.</html>",
            },
        ]
    }


def test_sync_persists_rows_and_sets_reply_fields(sqlite_session: Session) -> None:
    lid = uuid.uuid4()
    sqlite_session.add(
        Lead(
            id=lid,
            email="one@acme.test",
            hubspot_contact_id="hs-1",
            smartlead_lead_id="999",
            campaign_id="3154960",
        )
    )
    sqlite_session.commit()

    sl = FakeSmartleadMsgClient(_sample_history())
    hs = FakeHubSpot()
    r = sync_smartlead_message_history_for_lead(
        sqlite_session,
        sl,
        hs,
        lead_id=lid,
        campaign_id="3154960",
    )

    assert r.messages_upserted == 2
    assert r.has_inbound_reply is True
    assert r.reply_intent is None
    assert r.hubspot_patched is True
    assert r.smartlead_paused_count == 0
    assert hs.last_props is not None
    assert "sequence_status" not in hs.last_props
    assert hs.last_props.get("nombre_ultimo_mensaje") == "Hello"
    assert hs.last_props.get("ultima_respuesta_de_mensaje") == "Re: Hello"
    assert "last_sequence_step" not in hs.last_props
    assert "hs_email_last_email_name" not in hs.last_props
    assert "engagement_status" not in hs.last_props

    rows = list(sqlite_session.scalars(select(LeadMessageHistory).where(LeadMessageHistory.lead_id == lid)))
    assert len(rows) == 2
    by_mid = {r.message_id: r for r in rows}
    assert "<m1@partners.lanetahub.com>" in by_mid
    inbound = next(x for x in rows if x.direction == "inbound")
    assert inbound.reply_intent is None
    assert inbound.subject == "Re: Hello"
    body = inbound.email_body or ""
    assert "gmail_quote" not in body
    assert "Older thread" not in body
    assert "I am interested" in body
    assert body.strip().startswith("<div")


def test_legacy_messages_payload_still_syncs(sqlite_session: Session) -> None:
    lid = uuid.uuid4()
    sqlite_session.add(
        Lead(
            id=lid,
            email="legacy@acme.test",
            hubspot_contact_id=None,
            smartlead_lead_id="888",
            campaign_id="3154960",
        )
    )
    sqlite_session.commit()

    sl = FakeSmartleadMsgClient(_sample_messages_legacy())
    r = sync_smartlead_message_history_for_lead(
        sqlite_session,
        sl,
        None,
        lead_id=lid,
        campaign_id="3154960",
    )
    assert r.messages_upserted == 2
    assert r.has_inbound_reply is True


def test_interested_pauses_same_domain_peers(sqlite_session: Session) -> None:
    cid = "3154960"
    a = uuid.uuid4()
    b = uuid.uuid4()
    sqlite_session.add_all(
        [
            Lead(
                id=a,
                email="a@bigco.test",
                hubspot_contact_id="h1",
                smartlead_lead_id="101",
                campaign_id=cid,
            ),
            Lead(
                id=b,
                email="b@bigco.test",
                hubspot_contact_id="h2",
                smartlead_lead_id="102",
                campaign_id=cid,
            ),
        ]
    )
    sqlite_session.commit()

    sl = FakeSmartleadMsgClient(_sample_history())
    sync_smartlead_message_history_for_lead(sqlite_session, sl, None, lead_id=a, campaign_id=cid)

    assert sl.paused == []


def test_not_interested_pauses_only_one_lead(sqlite_session: Session) -> None:
    cid = "3154960"
    a = uuid.uuid4()
    b = uuid.uuid4()
    sqlite_session.add_all(
        [
            Lead(
                id=a,
                email="a@other.test",
                hubspot_contact_id="h1",
                smartlead_lead_id="201",
                campaign_id=cid,
            ),
            Lead(
                id=b,
                email="b@other.test",
                hubspot_contact_id="h2",
                smartlead_lead_id="202",
                campaign_id=cid,
            ),
        ]
    )
    sqlite_session.commit()

    msgs = [
        {
            "id": "o1",
            "subject": "Hi",
            "direction": "outbound",
            "sent_at": "2025-01-15T10:00:00Z",
        },
        {
            "id": "i1",
            "subject": "Re",
            "direction": "inbound",
            "received_at": "2025-01-16T10:00:00Z",
            "email_body": "Not interested, stop emailing",
        },
    ]
    sl = FakeSmartleadMsgClient({"messages": msgs})
    sync_smartlead_message_history_for_lead(sqlite_session, sl, None, lead_id=a, campaign_id=cid)

    assert sl.paused == []

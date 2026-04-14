from app.services.hubspot_lead_deal import (
    DEAL_STAGE_CONTACTADO,
    DEAL_STAGE_CERRADO_GANADO,
    DEAL_STAGE_CERRADO_PERDIDO,
    DEAL_STAGE_CUALIFICADO,
    DEAL_STAGE_REUNION_AGENDADA,
    _first_deal_id_from_contact_payload,
    resolve_deal_stage_id,
)


def test_email_sent_step_one_is_contactado():
    assert (
        resolve_deal_stage_id(
            sequence_status="active",
            category=None,
            opens=0,
            clicks=0,
            replies=0,
            last_sequence_step="1",
            last_event_type="EMAIL_SENT",
        )
        == DEAL_STAGE_CONTACTADO
    )


def test_completed_and_paused():
    assert (
        resolve_deal_stage_id(
            sequence_status="completed",
            category="meeting request",
            opens=0,
            clicks=0,
            replies=0,
            last_sequence_step="1",
            last_event_type="EMAIL_SENT",
        )
        == DEAL_STAGE_CERRADO_GANADO
    )
    assert (
        resolve_deal_stage_id(
            sequence_status="paused",
            category="interested",
            opens=5,
            clicks=0,
            replies=0,
            last_sequence_step="2",
            last_event_type="EMAIL_OPENED",
        )
        == DEAL_STAGE_CERRADO_PERDIDO
    )


def test_meeting_request_and_cualificado():
    assert (
        resolve_deal_stage_id(
            sequence_status="active",
            category="Meeting Request",
            opens=0,
            clicks=0,
            replies=1,
            last_sequence_step="1",
            last_event_type="EMAIL_REPLIED",
        )
        == DEAL_STAGE_REUNION_AGENDADA
    )
    assert (
        resolve_deal_stage_id(
            sequence_status="active",
            category="Interested",
            opens=1,
            clicks=0,
            replies=0,
            last_sequence_step="2",
            last_event_type="EMAIL_OPENED",
        )
        == DEAL_STAGE_CUALIFICADO
    )


def test_opens_without_interested_is_contactado():
    assert (
        resolve_deal_stage_id(
            sequence_status="active",
            category="Out Of Office",
            opens=1,
            clicks=0,
            replies=0,
            last_sequence_step="3",
            last_event_type="EMAIL_OPENED",
        )
        == DEAL_STAGE_CONTACTADO
    )


def test_first_deal_id_from_payload():
    assert (
        _first_deal_id_from_contact_payload(
            {"associations": {"deals": {"results": [{"id": "59153054330"}]}}},
        )
        == "59153054330"
    )
    assert (
        _first_deal_id_from_contact_payload(
            {"associations": {"deal": {"results": [{"id": "x"}]}}},
        )
        == "x"
    )

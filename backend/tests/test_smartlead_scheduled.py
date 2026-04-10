import uuid

from app.models.lead import Lead
from app.services.smartlead_scheduled import (
    list_active_smartlead_lead_ids,
    list_active_smartlead_lead_ids_for_campaign,
    list_distinct_campaign_ids_for_active_smartlead_leads,
)


def test_list_active_smartlead_lead_ids_filters_campaign_status_and_sl_id(sqlite_session):
    cid = "camp-1"
    a = uuid.uuid4()
    b = uuid.uuid4()
    c = uuid.uuid4()
    sqlite_session.add_all(
        [
            Lead(
                id=a,
                email="a@example.com",
                campaign_id=cid,
                smartlead_lead_id="sl-1",
                sequence_status="ACTIVE",
            ),
            Lead(
                id=b,
                email="b@example.com",
                campaign_id=cid,
                smartlead_lead_id="sl-2",
                sequence_status="paused",
            ),
            Lead(
                id=c,
                email="c@example.com",
                campaign_id="other",
                smartlead_lead_id="sl-3",
                sequence_status="active",
            ),
            Lead(
                id=uuid.uuid4(),
                email="d@example.com",
                campaign_id=cid,
                smartlead_lead_id=None,
                sequence_status="active",
            ),
        ]
    )
    sqlite_session.commit()

    ids = list_active_smartlead_lead_ids_for_campaign(sqlite_session, cid)
    assert ids == [a]


def test_list_active_smartlead_lead_ids_all_campaigns(sqlite_session):
    x = uuid.uuid4()
    y = uuid.uuid4()
    sqlite_session.add_all(
        [
            Lead(
                id=x,
                email="x@example.com",
                campaign_id="c1",
                smartlead_lead_id="1",
                sequence_status="active",
            ),
            Lead(
                id=y,
                email="y@example.com",
                campaign_id="c2",
                smartlead_lead_id="2",
                sequence_status="ACTIVE",
            ),
        ]
    )
    sqlite_session.commit()
    ids = list_active_smartlead_lead_ids(sqlite_session)
    assert set(ids) == {x, y}


def test_list_distinct_campaign_ids_for_active_smartlead_leads(sqlite_session):
    sqlite_session.add_all(
        [
            Lead(
                id=uuid.uuid4(),
                email="p@example.com",
                campaign_id="c1",
                smartlead_lead_id="1",
                sequence_status="active",
            ),
            Lead(
                id=uuid.uuid4(),
                email="q@example.com",
                campaign_id="c1",
                smartlead_lead_id="2",
                sequence_status="active",
            ),
            Lead(
                id=uuid.uuid4(),
                email="r@example.com",
                campaign_id="c2",
                smartlead_lead_id="3",
                sequence_status="paused",
            ),
        ]
    )
    sqlite_session.commit()
    assert list_distinct_campaign_ids_for_active_smartlead_leads(sqlite_session) == ["c1"]

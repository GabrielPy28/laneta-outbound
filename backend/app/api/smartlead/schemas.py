from pydantic import BaseModel, Field


class SmartleadPushCampaignResponse(BaseModel):
    campaign_id: str
    leads_selected: int
    batches_posted: int
    smartlead_added_count: int
    smartlead_skipped_count: int
    leads_resolved: int
    leads_unresolved: int
    db_updated: int
    hubspot_patched: int
    hubspot_failed: int
    hubspot_skipped_no_contact: int
    hubspot_available: bool = Field(
        description="False si no hay token HubSpot: solo se actualizó DB y Smartlead.",
    )
    errors: list[str] = Field(default_factory=list)


class SmartleadLeadStatisticsSyncResponse(BaseModel):
    campaign_id: str
    export_rows: int
    matched_leads: int
    statistics_upserted: int
    hubspot_patched: int
    hubspot_failed: int
    hubspot_skipped_no_contact: int
    hubspot_available: bool = Field(
        description="False si no hay token HubSpot: no se envió PATCH a HubSpot.",
    )
    errors: list[str] = Field(default_factory=list)


class MessageHistorySyncResponse(BaseModel):
    lead_id: str
    messages_upserted: int
    has_inbound_reply: bool
    reply_intent: str | None = None
    hubspot_patched: bool
    hubspot_available: bool = Field(
        description="False si no hay token HubSpot: no se envió PATCH a HubSpot.",
    )
    smartlead_paused_count: int
    errors: list[str] = Field(default_factory=list)

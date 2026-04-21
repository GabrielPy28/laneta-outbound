from pydantic import BaseModel, Field


class HubSpotNewLeadsSyncResponse(BaseModel):
    pages_fetched: int
    contacts_scanned: int
    created: int
    updated: int
    skipped_no_email: int
    hubspot_marked_done: int
    hubspot_mark_failed: int
    errors: list[str] = Field(default_factory=list)


class ManychatHubSpotSyncResponse(BaseModel):
    id_contact: str
    manychat_id: str | None = None
    hubspot_contact_id: str | None = None
    candidates_scanned: int
    matched_by: str | None = None
    hubspot_updated: bool
    manychat_updated: bool
    errors: list[str] = Field(default_factory=list)

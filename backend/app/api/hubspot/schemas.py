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

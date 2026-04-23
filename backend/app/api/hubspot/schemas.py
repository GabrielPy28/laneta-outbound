from __future__ import annotations
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field, model_validator

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


class CreateHubSpotCallRequest(BaseModel):
    crm_contact_id: str = Field(..., min_length=1)
    to_number: str = Field(..., min_length=1)
    from_number: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1)
    body: str = Field(..., min_length=1)
    call_start_time: datetime
    call_end_time: datetime

    @model_validator(mode="after")
    def end_after_start(self) -> CreateHubSpotCallRequest:
        if self.call_end_time < self.call_start_time:
            raise ValueError("call_end_time debe ser mayor o igual que call_start_time")
        return self


class CreateHubSpotCallResponse(BaseModel):
    id: str = Field(..., description="Id de la llamada (objeto call) en HubSpot")
    hs_body_preview: str | None = None
    hs_call_title: str | None = None
    hs_call_to_number: str | None = None
    hs_call_from_number: str | None = None
    hs_timestamp: str | None = None
    hubspot_contact_id: str = Field(
        ...,
        description="Id del contacto HubSpot encontrado por crm_contact_id",
    )


class HubSpotCallListItem(BaseModel):
    """Llamada con datos del contacto asociado (solo llamadas con associations.contacts)."""

    firstname: str | None = None
    lastname: str | None = None
    to_number: str | None = None
    from_number: str | None = None
    title: str | None = None
    description: str | None = None
    call_start_time: str | None = None
    call_end_time: str | None = None
    estatus_llamada: str | None = None


class CreateHubSpotMeetingRequest(BaseModel):
    crm_contact_id: str = Field(..., min_length=1)
    email: EmailStr
    title: str = Field(..., min_length=1)
    description: str = Field(..., min_length=1)
    additional_notes: str | None = None
    start_time: datetime
    end_time: datetime

    @model_validator(mode="after")
    def meeting_end_after_start(self) -> CreateHubSpotMeetingRequest:
        if self.end_time < self.start_time:
            raise ValueError("end_time debe ser mayor o igual que start_time")
        return self


class CreateHubSpotMeetingResponse(BaseModel):
    id: str = Field(..., description="Id de la reunión (objeto meeting) en HubSpot")
    hs_meeting_title: str | None = None
    hs_meeting_body: str | None = None
    hs_internal_meeting_notes: str | None = None
    hs_meeting_external_url: str | None = None
    hs_meeting_start_time: str | None = None
    hs_meeting_end_time: str | None = None
    hubspot_contact_id: str
    hubspot_deal_id: str | None = Field(
        None,
        description="Deal actualizado a etapa Reunión agendada (si existe)",
    )
    calendar_html_link: str = Field(
        ...,
        description="Mismo enlace enviado a HubSpot como hs_meeting_external_url (Google Calendar)",
    )


class HubSpotMeetingListItem(BaseModel):
    firstname: str | None = None
    lastname: str | None = None
    hs_meeting_title: str | None = None
    hs_meeting_body: str | None = None
    hs_internal_meeting_notes: str | None = None
    hs_meeting_external_url: str | None = None
    hs_meeting_start_time: str | None = None
    hs_meeting_end_time: str | None = None
    hubspot_deal_id: str | None = None

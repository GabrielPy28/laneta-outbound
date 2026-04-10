from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_session as get_session_generator
from app.integrations.hubspot.client import HubSpotClient

DbSession = Annotated[Session, Depends(get_session_generator)]


def get_hubspot_client_optional() -> HubSpotClient | None:
    settings = get_settings()
    token = settings.hubspot_access_token
    if not token or not str(token).strip():
        return None
    return HubSpotClient(access_token=str(token).strip())


OptionalHubSpotClient = Annotated[HubSpotClient | None, Depends(get_hubspot_client_optional)]

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from app.core.config import Settings

# Cobertura de creación / lectura de eventos en el calendario delegado
GOOGLE_CALENDAR_SCOPES: tuple[str, ...] = (
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/calendar.events",
)


class GoogleCalendarError(Exception):
    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        body: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.body = body


def _resolve_path(path_str: str) -> Path:
    p = Path(path_str.strip())
    return p if p.is_absolute() else Path.cwd() / p


def _client_id_secret_from_credentials_file(cred_path: Path) -> tuple[str | None, str | None]:
    if not cred_path.is_file():
        return None, None
    try:
        raw = json.loads(cred_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None, None
    block = raw.get("installed") or raw.get("web") or {}
    cid = block.get("client_id")
    secret = block.get("client_secret")
    return (
        str(cid).strip() if cid else None,
        str(secret).strip() if secret else None,
    )


def _load_credentials(settings: Settings) -> Credentials:
    cred_path = _resolve_path(settings.google_oauth_credentials_file)
    token_path = _resolve_path(settings.google_oauth_token_file)

    file_cid, file_secret = _client_id_secret_from_credentials_file(cred_path)
    client_id = (settings.google_oauth_client_id or "").strip() or file_cid
    client_secret = (settings.google_oauth_client_secret or "").strip() or file_secret
    refresh = (settings.google_oauth_refresh_token or "").strip() or None

    if refresh and client_id and client_secret:
        creds = Credentials(
            token=None,
            refresh_token=refresh,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=client_id,
            client_secret=client_secret,
            scopes=list(GOOGLE_CALENDAR_SCOPES),
        )
        creds.refresh(Request())
        try:
            token_path.write_text(creds.to_json(), encoding="utf-8")
        except OSError:
            pass
        return creds

    if not cred_path.is_file():
        raise GoogleCalendarError(
            f"No se encuentra el archivo de credenciales OAuth: {cred_path}. "
            "En Docker monta credentials.json o define GOOGLE_OAUTH_CLIENT_ID / "
            "GOOGLE_OAUTH_CLIENT_SECRET junto con GOOGLE_OAUTH_REFRESH_TOKEN.",
        )
    creds: Credentials | None = None
    if token_path.is_file():
        creds = Credentials.from_authorized_user_file(str(token_path), list(GOOGLE_CALENDAR_SCOPES))
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            try:
                token_path.write_text(creds.to_json(), encoding="utf-8")
            except OSError:
                pass
        else:
            raise GoogleCalendarError(
                "OAuth Google Calendar inválido o sin token.json. Opciones: "
                "(1) Genera token.json localmente (InstalledAppFlow) con scopes de Calendar y "
                "monta el archivo en el contenedor en la ruta configurada (GOOGLE_OAUTH_TOKEN_FILE). "
                "(2) Define GOOGLE_OAUTH_REFRESH_TOKEN; client_id/secret pueden salir de "
                "credentials.json o de GOOGLE_OAUTH_CLIENT_ID / GOOGLE_OAUTH_CLIENT_SECRET.",
            )
    return creds


def _format_google_datetime(dt: datetime, tz_name: str) -> str:
    """RFC3339 en la zona solicitada (p. ej. America/Mexico_City)."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    local = dt.astimezone(ZoneInfo(tz_name))
    return local.isoformat(timespec="seconds")


def insert_calendar_event(
    settings: Settings,
    *,
    title: str,
    description: str,
    contact_email: str,
    contact_display_name: str,
    start_time: datetime,
    end_time: datetime,
) -> dict[str, Any]:
    """
    Crea un evento en Google Calendar y devuelve el recurso completo (incluye htmlLink).
    """
    creds = _load_credentials(settings)
    try:
        service = build("calendar", "v3", credentials=creds, cache_discovery=False)
    except Exception as exc:
        raise GoogleCalendarError(f"No se pudo inicializar Calendar API: {exc}") from exc

    tz = settings.google_calendar_time_zone
    body: dict[str, Any] = {
        "summary": title,
        "description": description,
        "start": {
            "dateTime": _format_google_datetime(start_time, tz),
            "timeZone": tz,
        },
        "end": {
            "dateTime": _format_google_datetime(end_time, tz),
            "timeZone": tz,
        },
        "attendees": [
            {
                "displayName": settings.google_calendar_team_display_name,
                "email": settings.google_calendar_team_email,
                "additionalGuests": 2,
            },
            {
                "displayName": contact_display_name,
                "email": contact_email.strip(),
                "additionalGuests": 2,
            },
        ],
        "guestsCanInviteOthers": True,
        "creator": {
            "displayName": settings.google_calendar_team_display_name,
            "email": settings.google_calendar_team_email,
        },
        "eventType": "default",
    }

    cal_id = settings.google_calendar_id.strip()
    try:
        # https://developers.google.com/calendar/api/v3/reference/events/insert
        created = (
            service.events()
            .insert(
                calendarId=cal_id,
                body=body,
                conferenceDataVersion=1,
                maxAttendees=8,
                sendUpdates="none",
            )
            .execute()
        )
    except HttpError as exc:
        err_text = getattr(exc, "content", None) or str(exc)
        raise GoogleCalendarError(
            f"Google Calendar insert falló: {exc!s}",
            status_code=getattr(exc.resp, "status", None),
            body=str(err_text)[:2000],
        ) from exc
    if not isinstance(created, dict):
        raise GoogleCalendarError("Google Calendar devolvió un formato inesperado.")
    return created

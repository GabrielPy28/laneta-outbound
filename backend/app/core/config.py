from functools import lru_cache
from typing import Literal

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = Field(
        validation_alias=AliasChoices("DATABASE_URL", "SUPABASE_DB_URL"),
    )
    database_echo: bool = Field(default=False, validation_alias="DATABASE_ECHO")
    database_create_tables: bool = Field(
        default=False,
        validation_alias="DATABASE_CREATE_TABLES",
    )

    redis_url: str = Field(
        default="redis://localhost:6379/0",
        validation_alias="REDIS_URL",
    )

    hubspot_access_token: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "HUBSPOT_ACCESS_TOKEN",
            "HUBSPOT_API_KEY",
            "HUBSPOT_PRIVATE_APP_TOKEN",
        ),
    )
    hubspot_call_contact_association_type_id: int = Field(
        default=194,
        validation_alias="HUBSPOT_CALL_CONTACT_ASSOCIATION_TYPE_ID",
        description=(
            "ID de asociación HubSpot (HUBSPOT_DEFINED) entre objetos call y contact. "
            "Puede variar por portal; solemos usar 194 en la ruta PUT y en el cuerpo."
        ),
    )
    smartlead_api_key: str | None = Field(
        default=None,
        validation_alias="SMARTLEAD_API_KEY",
    )
    smartlead_campaign_id: str | None = Field(
        default=None,
        validation_alias=AliasChoices("ID_CAMPAIGN", "SMARTLEAD_CAMPAIGN_ID"),
        description="Obsoleto: el ID de campaña para nuevas altas vive en la tabla `campaign_active`.",
    )
    manychat_api_key: str | None = Field(
        default=None,
        validation_alias="MANYCHAT_API_KEY",
    )

    schedule_hubspot_sync_seconds: int = Field(
        default=2_700,  # ← 45 MINUTOS
        ge=300,         # 5 min mínimo (evita spam)
        le=86_400,      # 24h máximo
        validation_alias="SCHEDULE_HUBSPOT_SYNC_SECONDS",
        description="""Intervalo sync HubSpot (segundos).
        - Default: 45 min (2,700s)
        - Min: 5 min (300s) 
        - Max: 24h (86,400s)"""
    )

    schedule_smartlead_active_seconds: int = Field(
        default=3_600,
        ge=120,
        le=86_400,
        validation_alias="SCHEDULE_SMARTLEAD_ACTIVE_SECONDS",
        description="Intervalo stats export + message-history para leads ACTIVE (seg.). Por defecto 1 h.",
    )

    environment: Literal["development", "staging", "production"] = Field(
        default="development",
        validation_alias="ENVIRONMENT",
    )

    supabase_url: str | None = Field(default=None, validation_alias="SUPABASE_URL")
    supabase_public_key: str | None = Field(
        default=None,
        validation_alias="SUPABASE_PUBLIC_KEY",
        description="Clave anon (pública) del proyecto Supabase.",
    )
    supabase_secret_key: str | None = Field(
        default=None,
        validation_alias="SUPABASE_SECRET_KEY",
        description="Clave service_role u otra clave secreta; preferida sobre la pública en servidor.",
    )

    jwt_secret_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("JWT_SECRET_KEY", "SECRET_KEY"),
        description="Secreto HS256 para firmar el access_token del frontend.",
    )
    jwt_algorithm: str = Field(default="HS256", validation_alias="JWT_ALGORITHM")
    jwt_expire_minutes: int = Field(
        default=60 * 24,
        ge=5,
        le=60 * 24 * 30,
        validation_alias="JWT_EXPIRE_MINUTES",
    )

    cors_origins: str = Field(
        default="http://localhost:5173,http://127.0.0.1:5173",
        validation_alias="CORS_ORIGINS",
        description="Orígenes permitidos CORS, separados por coma (frontend).",
    )

    google_oauth_credentials_file: str = Field(
        default="credentials.json",
        validation_alias="GOOGLE_OAUTH_CREDENTIALS_FILE",
        description="Ruta al OAuth client JSON (desde el cwd del proceso, p. ej. carpeta backend/).",
    )
    google_oauth_token_file: str = Field(
        default="token.json",
        validation_alias="GOOGLE_OAUTH_TOKEN_FILE",
        description="Token OAuth del usuario/calendario (refresh); relativo al cwd.",
    )
    google_calendar_id: str = Field(
        default="sistemas@laneta.com",
        validation_alias="GOOGLE_CALENDAR_ID",
        description="calendarId en Calendar API donde se crean los eventos.",
    )
    google_calendar_team_email: str = Field(
        default="sistemas@laneta.com",
        validation_alias="GOOGLE_CALENDAR_TEAM_EMAIL",
    )
    google_calendar_team_display_name: str = Field(
        default="La Neta Team",
        validation_alias="GOOGLE_CALENDAR_TEAM_DISPLAY_NAME",
    )
    google_calendar_time_zone: str = Field(
        default="America/Mexico_City",
        validation_alias="GOOGLE_CALENDAR_TIME_ZONE",
    )
    google_oauth_client_id: str | None = Field(
        default=None,
        validation_alias="GOOGLE_OAUTH_CLIENT_ID",
        description="OAuth client_id (opcional si está en credentials.json).",
    )
    google_oauth_client_secret: str | None = Field(
        default=None,
        validation_alias="GOOGLE_OAUTH_CLIENT_SECRET",
        description="OAuth client_secret (opcional si está en credentials.json).",
    )
    google_oauth_refresh_token: str | None = Field(
        default=None,
        validation_alias="GOOGLE_OAUTH_REFRESH_TOKEN",
        description=(
            "Refresh token de usuario con scopes de Calendar; útil en Docker sin token.json. "
            "Se puede combinar con credentials.json solo para client_id/secret."
        ),
    )
    domains_registry_file: str = Field(
        default="domains.json",
        validation_alias="DOMAINS_REGISTRY_FILE",
        description="Ruta al catálogo de dominios (formato domains.json) usado para validación interna.",
    )

    postmaster_beat_enabled: bool = Field(
        default=True,
        validation_alias="POSTMASTER_BEAT_ENABLED",
        description="Si es false, Celery Beat no registra la tarea periódica de chequeo Postmaster.",
    )
    postmaster_beat_hour_utc: int = Field(
        default=14,
        ge=0,
        le=23,
        validation_alias="POSTMASTER_BEAT_HOUR_UTC",
        description=(
            "Hora UTC para crontab del job Postmaster (default 14 = 08:30 en America/Mexico_City con UTC-6)."
        ),
    )
    postmaster_beat_minute_utc: int = Field(
        default=30,
        ge=0,
        le=59,
        validation_alias="POSTMASTER_BEAT_MINUTE_UTC",
        description="Minuto UTC para el job Postmaster.",
    )
    postmaster_beat_day_of_week: str = Field(
        default="1,3,5",
        validation_alias="POSTMASTER_BEAT_DAY_OF_WEEK",
        description="Crontab day_of_week (0=domingo): 1,3,5 = lunes, miércoles, viernes.",
    )

    smtp_host: str = Field(
        default="smtp.gmail.com",
        validation_alias="SMTP_HOST",
        description="Servidor SMTP (Google Workspace / Gmail: smtp.gmail.com).",
    )
    smtp_port: int = Field(
        default=587,
        ge=1,
        le=65535,
        validation_alias="SMTP_PORT",
        description="587 + STARTTLS habitual en Gmail; 465 con SMTP_SSL si smtp_use_ssl=true.",
    )
    smtp_use_ssl: bool = Field(
        default=False,
        validation_alias="SMTP_USE_SSL",
        description="Si es true, usa SMTP_SSL (típico puerto 465); si false, SMTP + STARTTLS.",
    )
    smtp_user: str | None = Field(
        default=None,
        validation_alias="SMTP_USER",
        description="Usuario SMTP (ej. gabriel@laneta.com).",
    )
    smtp_password: str | None = Field(
        default=None,
        validation_alias="SMTP_PASSWORD",
        description="Contraseña de aplicación o secreto SMTP.",
    )
    postmaster_report_to_email: str = Field(
        default="domain-status@laneta.com",
        validation_alias="POSTMASTER_REPORT_TO_EMAIL",
        description="Destinatario del resumen Postmaster enviado por el job programado.",
    )

    @field_validator("database_url", mode="before")
    @classmethod
    def normalize_database_url(cls, v: str) -> str:
        if not isinstance(v, str):
            return v
        # .env / --env-file a veces dejan comillas literales; SQLAlchemy no las acepta.
        url = v.strip().strip('"').strip("'").strip()
        if url.startswith("postgres://"):
            url = "postgresql://" + url.removeprefix("postgres://")
        return url

    @property
    def sqlalchemy_database_uri(self) -> str:
        """URI para el driver psycopg v3 (paquete `psycopg`, no psycopg2)."""
        url = str(self.database_url)
        if url.startswith("postgresql+psycopg2://"):
            url = "postgresql+psycopg://" + url.removeprefix("postgresql+psycopg2://")
        if url.startswith("postgresql+psycopg"):
            return url
        if url.startswith("postgresql://"):
            return "postgresql+psycopg://" + url.removeprefix("postgresql://")
        return url


@lru_cache
def get_settings() -> Settings:
    return Settings()

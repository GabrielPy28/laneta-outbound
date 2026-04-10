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
    smartlead_api_key: str | None = Field(
        default=None,
        validation_alias="SMARTLEAD_API_KEY",
    )
    smartlead_campaign_id: str | None = Field(
        default=None,
        validation_alias=AliasChoices("ID_CAMPAIGN", "SMARTLEAD_CAMPAIGN_ID"),
        description="Obsoleto: el ID de campaña para nuevas altas vive en la tabla `campaign_active`.",
    )

    schedule_hubspot_sync_seconds: int = Field(
        default=18_000,
        ge=3_600,
        le=86_400,
        validation_alias="SCHEDULE_HUBSPOT_SYNC_SECONDS",
        description="Intervalo entre sync HubSpot + push (seg.). Por defecto 5 h (rango 4–6 h vía env).",
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

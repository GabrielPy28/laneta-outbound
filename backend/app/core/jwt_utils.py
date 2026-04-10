"""JWT de acceso para el frontend (independiente del JWT de Supabase)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import jwt

from app.core.config import get_settings


def decode_access_token(token: str) -> dict[str, Any]:
    """Decodifica y valida firma y expiración. Lanza `jwt.PyJWTError` si falla."""
    settings = get_settings()
    secret = (settings.jwt_secret_key or "").strip()
    if not secret:
        raise ValueError("Configure JWT_SECRET_KEY en .env para validar tokens de API.")
    return jwt.decode(
        token,
        secret,
        algorithms=[settings.jwt_algorithm],
    )


def create_access_token(*, sub: str, email: str, name: str) -> str:
    settings = get_settings()
    secret = (settings.jwt_secret_key or "").strip()
    if not secret:
        raise ValueError("Configure JWT_SECRET_KEY en .env para emitir tokens de API.")

    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {
        "sub": sub,
        "email": email,
        "name": name,
        "iat": now,
        "exp": expire,
    }
    return jwt.encode(
        payload,
        secret,
        algorithm=settings.jwt_algorithm,
    )

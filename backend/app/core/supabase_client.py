"""Cliente Supabase para Auth (sign_in_with_password) y lectura de tablas."""

from supabase import Client, create_client

from app.core.config import get_settings


def get_supabase_client() -> Client:
    """Cliente con `SUPABASE_SECRET_KEY` o `SUPABASE_PUBLIC_KEY` (anon)."""
    settings = get_settings()
    url = (settings.supabase_url or "").strip()
    if not url:
        raise ValueError("Configure SUPABASE_URL en .env")
    key = (settings.supabase_secret_key or settings.supabase_public_key or "").strip()
    if not key:
        raise ValueError("Configure SUPABASE_SECRET_KEY o SUPABASE_PUBLIC_KEY en .env")
    return create_client(url, key)

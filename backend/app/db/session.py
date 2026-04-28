from __future__ import annotations

import os
from collections.abc import Generator
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings

_settings = get_settings()


class Base(DeclarativeBase):
    pass


def _sanitize_psycopg2_url(url: str) -> str:
    """libpq no acepta el parámetro pgbouncer (solo lo usan clientes como Prisma)."""
    if "pgbouncer" not in url.lower():
        return url
    parsed = urlparse(url)
    q = [
        (k, v)
        for k, v in parse_qsl(parsed.query, keep_blank_values=True)
        if k.lower() != "pgbouncer"
    ]
    return urlunparse(parsed._replace(query=urlencode(q)))


def _is_transaction_pooler_url(url: str) -> bool:
    u = url.lower()
    return ":6543" in u or ".pooler.supabase.com" in u


def _pooler_connect_args(url: str) -> dict:
    """
    PgBouncer (modo transacción) + psycopg: sin prepared statements.
    Keepalives TCP: reduce cortes SSL SYSCALL / EOF por NAT o idle largo.
    """
    args: dict = {}
    if _is_transaction_pooler_url(url):
        args["prepare_threshold"] = None
        args["keepalives"] = 1
        args["keepalives_idle"] = 30
        args["keepalives_interval"] = 10
        args["keepalives_count"] = 5
    return args


def _pool_recycle_seconds(url: str) -> int:
    """
    Reciclar conexiones antes de que el pooler (p. ej. Supabase) las cierre.
    DB_POOL_RECYCLE en segundos sobrescribe el valor automático.
    """
    raw = os.getenv("DB_POOL_RECYCLE", "").strip()
    if raw:
        try:
            return max(30, int(raw))
        except ValueError:
            pass
    return 280 if _is_transaction_pooler_url(url) else 1800


_db_url = _sanitize_psycopg2_url(_settings.sqlalchemy_database_uri)
_connect_args = _pooler_connect_args(_db_url)

engine: Engine = create_engine(
    _db_url,
    echo=_settings.database_echo,
    pool_pre_ping=True,
    pool_recycle=_pool_recycle_seconds(_db_url),
    connect_args=_connect_args,
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    class_=Session,
)


def database_engine_url() -> str:
    """URL efectiva del engine (sanitizada); útil p. ej. para Alembic offline."""
    return _db_url


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Compatibilidad con dependencias existentes
get_session = get_db


def create_session() -> Session:
    """Sesión nueva (p. ej. workers Celery). El llamador debe cerrarla."""
    return SessionLocal()


def check_connection() -> None:
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))


def create_tables() -> None:
    from app.models import (  # noqa: F401
        CampaignActive,
        Lead,
        LeadDeal,
        LeadMessageHistory,
        LeadStatistics,
        PostmasterReport,
    )

    Base.metadata.create_all(bind=engine)


def dispose_engine() -> None:
    engine.dispose()

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.models.campaign_active import CampaignActive  # noqa: F401
from app.models.lead import Lead
from app.models.lead_deal import LeadDeal  # noqa: F401
from app.models.lead_statistics import LeadStatistics  # noqa: F401
from app.models.lead_message_history import LeadMessageHistory  # noqa: F401


@pytest.fixture
def sqlite_session() -> Session:
    """Sesión sobre SQLite en memoria (tabla `leads`); útil para probar la ingesta sin Postgres.

    StaticPool + check_same_thread=False: TestClient ejecuta rutas en un hilo distinto y
    :memory: por defecto no compartiría la misma BD entre conexiones.
    """
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, class_=Session)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()

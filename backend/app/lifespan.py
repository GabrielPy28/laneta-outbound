import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.config import get_settings

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.db.session import check_connection, create_tables, dispose_engine

    settings = get_settings()
    try:
        await asyncio.to_thread(check_connection)
        logger.info("Conexión a la base de datos verificada.")
    except Exception:
        logger.exception("No se pudo conectar a la base de datos.")
        raise

    if settings.database_create_tables:
        await asyncio.to_thread(create_tables)
        logger.info("Tablas ORM sincronizadas (create_all).")

    yield

    await asyncio.to_thread(dispose_engine)
    logger.info("Motor SQLAlchemy cerrado.")

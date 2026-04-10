"""El `DeclarativeBase` vive en `session.py` junto al engine; aquí solo re-exportamos."""

from app.db.session import Base

__all__ = ("Base",)

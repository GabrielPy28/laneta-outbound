import pytest

from app.core.config import get_settings
from app.core.jwt_utils import create_access_token


def test_create_access_token_requires_jwt_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    # Vacío en proceso sobrescribe valores del `.env` de desarrollo (pydantic: env > archivo).
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@localhost:5432/db")
    monkeypatch.setenv("JWT_SECRET_KEY", "")
    monkeypatch.setenv("SECRET_KEY", "")
    get_settings.cache_clear()

    with pytest.raises(ValueError, match="JWT_SECRET_KEY"):
        create_access_token(sub="user-1", email="a@b.com", name="A")


def test_create_access_token_roundtrip(monkeypatch: pytest.MonkeyPatch) -> None:
    get_settings.cache_clear()
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@localhost:5432/db")
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-for-unit-tests")

    token = create_access_token(sub="user-1", email="a@b.com", name="Test User")
    assert isinstance(token, str) and len(token) > 20

    import jwt

    payload = jwt.decode(
        token,
        "test-secret-for-unit-tests",
        algorithms=[get_settings().jwt_algorithm],
    )
    assert payload["sub"] == "user-1"
    assert payload["email"] == "a@b.com"
    assert payload["name"] == "Test User"

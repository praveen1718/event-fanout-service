from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

import app.db.engine as engine_module
from app.core.config import get_settings
from app.main import create_app


def _reset_singletons() -> None:
    get_settings.cache_clear()
    engine_module._engine = None
    engine_module._session_factory = None


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    """App wired to a fresh throwaway SQLite file, exercising the real startup path.

    raise_server_exceptions=False so tests observe the 500 the client would see
    instead of the raw exception.
    """
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/test.db")
    _reset_singletons()
    with TestClient(create_app(), raise_server_exceptions=False) as test_client:
        yield test_client
    _reset_singletons()


@pytest.fixture
def db_session(client: TestClient) -> Iterator[Session]:
    """Direct DB access for asserting on persisted state."""
    session = engine_module.get_session_factory()()
    try:
        yield session
    finally:
        session.close()

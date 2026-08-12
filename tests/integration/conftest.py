from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def db_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "baymax.db"
    monkeypatch.setenv("BAYMAX_DB_PATH", str(path))
    return path


@pytest.fixture
def client_factory(db_path: Path):
    from server.app import app
    from server.db import initialize_database

    initialize_database()

    def create_client() -> TestClient:
        return TestClient(app)

    return create_client


@pytest.fixture
def client(client_factory) -> Iterator[TestClient]:
    with client_factory() as test_client:
        yield test_client

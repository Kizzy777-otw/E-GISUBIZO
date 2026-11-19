"""Shared isolated configuration for API tests."""

import os
from pathlib import Path
import tempfile
from uuid import uuid4

import pytest


_TEST_DATABASE = Path(tempfile.gettempdir()) / f"egisubizo-test-{uuid4().hex}.db"
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DATABASE.as_posix()}"
os.environ["APP_ENV"] = "test"
os.environ.pop("VERCEL", None)
os.environ["ADMIN_API_TOKEN"] = "test-admin-token"
os.environ["TECHNICIAN_API_TOKEN"] = "test-technician-token"
os.environ["ADMIN_PASSWORD"] = "test-admin-password"
os.environ["TECHNICIAN_PASSWORD"] = "test-tech-password"

from fastapi.testclient import TestClient

from backend.main import app
from backend.database import engine


@pytest.fixture(scope="session")
def api_client():
    with TestClient(app) as client:
        yield client


@pytest.fixture(scope="session", autouse=True)
def remove_test_database():
    yield
    engine.dispose()
    _TEST_DATABASE.unlink(missing_ok=True)

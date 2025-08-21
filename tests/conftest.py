# tests/conftest.py
import os
import tempfile
import pytest
from starlette.testclient import TestClient

@pytest.fixture(scope="session")
def tmp_db_path():
    with tempfile.TemporaryDirectory() as d:
        yield os.path.join(d, "test.sqlite3")  # auto-deleted after session

@pytest.fixture(scope="session")
def app(tmp_db_path, monkeypatch):
    # Point ALL app DB work to the temp file before importing app/db
    monkeypatch.setenv("ATM_DB_PATH", tmp_db_path)

    # Import after env is set so modules see test DB
    from src import db
    db.reset_connection()   # drop any cached conn that might keep old path
    db.init_db()            # create schema in temp DB

    # Optional: disable any auto-seed-on-startup in tests
    # monkeypatch.setenv("ATM_DISABLE_SEED", "1")

    from src.app import create_app
    return create_app()

@pytest.fixture(autouse=True)
def clean_db():
    # Clean rows before/after each test (does NOT touch dev DB)
    from src import db
    db.truncate_all()
    yield
    db.truncate_all()

@pytest.fixture()
def client(app):
    return TestClient(app)
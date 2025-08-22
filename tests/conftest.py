# tests/conftest.py
import os
import tempfile
import pytest
from starlette.testclient import TestClient

from src.app import create_app
from src import db

@pytest.fixture(scope="session")
def tmp_db_path():
    with tempfile.TemporaryDirectory() as d:
        yield os.path.join(d, "test.sqlite3")  # removed automatically

@pytest.fixture(scope="session")
def app(tmp_db_path):
    os.environ["ATM_DB_PATH"] = tmp_db_path     # <-- TEST-ONLY DB
    db.reset_connection()                       # if you cache a conn
    db.init_db()
    return create_app()

@pytest.fixture(autouse=True)
def clean_db():
    db.truncate_all()   # isolation between tests
    yield
    db.truncate_all()

@pytest.fixture()
def client(app):
    return TestClient(app)
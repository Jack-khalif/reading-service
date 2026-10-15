import os

import psycopg
import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient

# Tests get their own database so they can never wipe your dev data.
TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql://postgres@localhost:5432/readings_test"
)


@pytest.fixture(scope="session", autouse=True)
def migrated_database():
    """Build the schema once per test run, the same way production does:
    by running the Alembic migrations, not a hand-written CREATE TABLE."""
    os.environ["DATABASE_URL"] = TEST_DATABASE_URL
    command.upgrade(Config("alembic.ini"), "head")


@pytest.fixture
def client():
    """Empty readings table per test, so tests can't interfere with each other."""
    with psycopg.connect(TEST_DATABASE_URL) as conn:
        conn.execute("TRUNCATE readings")

    from app.main import app

    # raise_server_exceptions=False: an unhandled exception in the app
    # should come back as a real HTTP 500 response, the way it would in
    # production behind a real ASGI server -- not as a Python exception
    # raised inside the test client, which would hide the failure from
    # our assertions on status codes.
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c

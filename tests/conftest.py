import os
import tempfile

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """Fresh SQLite file per test, so tests can't interfere with each other."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    os.environ["READINGS_DB_PATH"] = path

    # Import after env var is set, and reload so app picks up the fresh path.
    import app.main as main_module
    import importlib
    importlib.reload(main_module)

    # raise_server_exceptions=False: an unhandled exception in the app
    # should come back as a real HTTP 500 response, the way it would in
    # production behind a real ASGI server -- not as a Python exception
    # raised inside the test client, which would hide the failure from
    # our assertions on status codes.
    with TestClient(main_module.app, raise_server_exceptions=False) as c:
        yield c

    os.remove(path)

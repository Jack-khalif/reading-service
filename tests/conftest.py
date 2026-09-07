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

    with TestClient(main_module.app) as c:
        yield c

    os.remove(path)

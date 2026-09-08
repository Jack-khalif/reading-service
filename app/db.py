"""
SQLite storage layer for device readings.
"""
import sqlite3
from contextlib import contextmanager
from pathlib import Path

CLOCK_SKEW_TOLERANCE_SECONDS = 120

SCHEMA = """
CREATE TABLE IF NOT EXISTS readings (
    reading_id      TEXT PRIMARY KEY,
    device_id       TEXT NOT NULL,
    metric          TEXT NOT NULL,
    value           REAL NOT NULL,
    recorded_at     TEXT NOT NULL,
    arrived_at      TEXT NOT NULL,
    clock_anomaly   INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_device_metric_time
    ON readings (device_id, metric, recorded_at);
"""


def init_db(db_path: str) -> None:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    with get_conn(db_path) as conn:
        conn.executescript(SCHEMA)


@contextmanager
def get_conn(db_path: str):
    conn = sqlite3.connect(db_path, timeout=5, check_same_thread=False)
    conn.execute("PRAGMA busy_timeout = 5000")
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()
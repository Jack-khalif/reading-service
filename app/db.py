"""
SQLite storage layer for device readings.

Design notes:
- reading_id is the PRIMARY KEY. This is what gives us idempotency:
  the same reading sent twice can never exist as two rows, because SQLite
  itself enforces the uniqueness -- we don't rely on application logic to
  "remember" what it has already seen.
- We store both `recorded_at` (when the device says the reading happened)
  and `arrived_at` (when our server actually received it) as separate
  columns. "Latest reading" queries always sort by recorded_at, never
  arrived_at, per the spec.
- `clock_anomaly` is a derived flag set at insert time when a device's
  recorded_at is implausibly in the future relative to when we received it
  (allowing a small tolerance for normal clock drift/network latency).
  We still store these readings (we don't want to silently drop data) but
  we exclude them from "latest reading" by default, since a device with a
  broken clock could otherwise permanently poison that answer.
"""
import sqlite3
from contextlib import contextmanager
from pathlib import Path

# Tolerance for how far into the future a recorded_at can be before we
# treat it as a clock problem rather than normal jitter.
CLOCK_SKEW_TOLERANCE_SECONDS = 120

SCHEMA = """
CREATE TABLE IF NOT EXISTS readings (
    reading_id      TEXT PRIMARY KEY,
    device_id       TEXT NOT NULL,
    metric          TEXT NOT NULL,
    value           REAL NOT NULL,
    recorded_at     TEXT NOT NULL,
    arrived_at      TEXT NOT NULL,
    clock_anomaly   INTEGER NOT NULL DEFAULT 0,
    
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
    # `check_same_thread=False` because FastAPI/uvicorn may serve requests
    # on different threads; each call still gets its own short-lived
    # connection, and busy_timeout lets concurrent writers queue instead
    # of immediately raising "database is locked".
    conn = sqlite3.connect(db_path, timeout=5, check_same_thread=False)
    conn.execute("PRAGMA busy_timeout = 5000")
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()

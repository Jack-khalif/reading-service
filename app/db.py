"""
PostgreSQL storage layer for device readings.

The schema itself lives in Alembic migrations (see `migrations/`), not here.
This module only knows how to hand out connections.
"""
import os

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

CLOCK_SKEW_TOLERANCE_SECONDS = 120

DEFAULT_DATABASE_URL = "postgresql://postgres@localhost:5432/readings"

POOL_SIZE = int(os.environ.get("DB_POOL_SIZE", "10"))


def get_database_url() -> str:
    return os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)


def create_pool(database_url: str) -> ConnectionPool:
    # A pool keeps a handful of open connections and lends one to each
    # request, instead of paying for a new TCP connection + Postgres backend
    # process on every request. Concurrent requests get *different*
    # connections, so the database -- not Python -- decides who wins when
    # two of them insert the same reading_id.
    #
    # Fixed size (min == max) on purpose: with min_size=1, concurrent
    # requests queue for the one warm connection while the pool slowly
    # grows, which quietly serialises them -- and hid the check-then-insert
    # race from tests/test_concurrency.py entirely (0/20 failures, vs 19/20
    # with all connections open up front).
    return ConnectionPool(
        database_url,
        min_size=POOL_SIZE,
        max_size=POOL_SIZE,
        # Every session runs in UTC, so TIMESTAMPTZ values come back as
        # UTC datetimes regardless of the server's configured timezone.
        kwargs={"row_factory": dict_row, "options": "-c timezone=UTC"},
        open=False,
    )

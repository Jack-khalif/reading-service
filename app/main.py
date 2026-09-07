import os
from datetime import datetime, timezone, timedelta

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse

from app.db import get_conn, init_db, CLOCK_SKEW_TOLERANCE_SECONDS
from app.models import ReadingIn

DB_PATH = os.environ.get("READINGS_DB_PATH", "readings.db")

app = FastAPI(title="Device Reading Service")


@app.on_event("startup")
def _startup():
    init_db(DB_PATH)


def _parse_iso(ts: str) -> datetime:
    dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


@app.post("/readings", status_code=201)
def ingest_reading(reading: ReadingIn):
    now = datetime.now(timezone.utc)
    recorded_at = _parse_iso(reading.recorded_at)
    is_anomaly = (recorded_at - now) > timedelta(seconds=CLOCK_SKEW_TOLERANCE_SECONDS)

    with get_conn(DB_PATH) as conn:
        # Atomic insert-or-ignore instead of "check then insert": the
        # uniqueness decision is made by SQLite itself as part of a single
        # statement, so there's no window between "check" and "act" for a
        # second concurrent request to slip into. `changes()` tells us
        # whether this call was the one that actually inserted the row.
        conn.execute(
            """INSERT OR IGNORE INTO readings
               (reading_id, device_id, metric, value, recorded_at, arrived_at, clock_anomaly)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                reading.reading_id,
                reading.device_id,
                reading.metric,
                reading.value,
                reading.recorded_at,
                now.isoformat(),
                int(is_anomaly),
            ),
        )
        inserted = conn.execute("SELECT changes()").fetchone()[0]

    if inserted:
        return {"status": "created"}
    return JSONResponse(status_code=200, content={"status": "duplicate"})


@app.get("/devices/{device_id}/metrics/{metric}/latest")
def latest_reading(device_id: str, metric: str):
    with get_conn(DB_PATH) as conn:
        row = conn.execute(
            """SELECT * FROM readings
               WHERE device_id = ? AND metric = ? AND clock_anomaly = 0
               ORDER BY recorded_at DESC LIMIT 1""",
            (device_id, metric),
        ).fetchone()

        anomaly_fallback = False
        if row is None:
            # Every reading we have for this device/metric had a bad clock.
            # Fall back to it rather than pretending we have no data, but
            # say so explicitly.
            row = conn.execute(
                """SELECT * FROM readings
                   WHERE device_id = ? AND metric = ?
                   ORDER BY recorded_at DESC LIMIT 1""",
                (device_id, metric),
            ).fetchone()
            anomaly_fallback = row is not None

    if row is None:
        raise HTTPException(status_code=404, detail="No readings for this device/metric")

    result = dict(row)
    result["clock_anomaly"] = bool(result["clock_anomaly"])
    if anomaly_fallback:
        result["warning"] = "only clock-anomalous readings available"
    return result


@app.get("/devices/{device_id}/readings")
def readings_in_range(
    device_id: str,
    start: str = Query(..., description="ISO-8601 UTC start of range (inclusive)"),
    end: str = Query(..., description="ISO-8601 UTC end of range (inclusive)"),
    metric: str | None = Query(None),
):
    query = "SELECT * FROM readings WHERE device_id = ? AND recorded_at >= ? AND recorded_at <= ?"
    params = [device_id, start, end]
    if metric:
        query += " AND metric = ?"
        params.append(metric)
    query += " ORDER BY recorded_at ASC"

    with get_conn(DB_PATH) as conn:
        rows = conn.execute(query, params).fetchall()

    return [
        {**dict(r), "clock_anomaly": bool(r["clock_anomaly"])} for r in rows
    ]

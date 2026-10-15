from contextlib import asynccontextmanager
from datetime import datetime, timezone, timedelta

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse

from app.db import CLOCK_SKEW_TOLERANCE_SECONDS, create_pool, get_database_url
from app.models import ReadingIn


@asynccontextmanager
async def lifespan(app: FastAPI):
    # The schema is NOT created here -- run `alembic upgrade head` first.
    app.state.pool = create_pool(get_database_url())
    app.state.pool.open(wait=True)
    try:
        yield
    finally:
        app.state.pool.close()


app = FastAPI(title="Device Reading Service", lifespan=lifespan)


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _row_to_json(row: dict) -> dict:
    return {**row, "recorded_at": _iso(row["recorded_at"]), "arrived_at": _iso(row["arrived_at"])}


@app.post("/readings", status_code=201)
def ingest_reading(reading: ReadingIn):
    now = datetime.now(timezone.utc)
    is_anomaly = (reading.recorded_at - now) > timedelta(seconds=CLOCK_SKEW_TOLERANCE_SECONDS)

    with app.state.pool.connection() as conn:
        # Atomic insert-or-ignore instead of "check then insert": the
        # uniqueness decision is made by Postgres itself as part of a single
        # statement, so there's no window between "check" and "act" for a
        # second concurrent request to slip into. RETURNING only produces a
        # row if this call actually inserted one; on conflict it's empty.
        inserted = conn.execute(
            """INSERT INTO readings
               (reading_id, device_id, metric, value, recorded_at, arrived_at, clock_anomaly)
               VALUES (%s, %s, %s, %s, %s, %s, %s)
               ON CONFLICT (reading_id) DO NOTHING
               RETURNING reading_id""",
            (
                reading.reading_id,
                reading.device_id,
                reading.metric,
                reading.value,
                reading.recorded_at,
                now,
                is_anomaly,
            ),
        ).fetchone()

    if inserted:
        return {"status": "created"}
    return JSONResponse(status_code=200, content={"status": "duplicate"})


@app.get("/devices/{device_id}/metrics/{metric}/latest")
def latest_reading(device_id: str, metric: str):
    with app.state.pool.connection() as conn:
        row = conn.execute(
            """SELECT * FROM readings
               WHERE device_id = %s AND metric = %s AND NOT clock_anomaly
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
                   WHERE device_id = %s AND metric = %s
                   ORDER BY recorded_at DESC LIMIT 1""",
                (device_id, metric),
            ).fetchone()
            anomaly_fallback = row is not None

    if row is None:
        raise HTTPException(status_code=404, detail="No readings for this device/metric")

    result = _row_to_json(row)
    if anomaly_fallback:
        result["warning"] = "only clock-anomalous readings available"
    return result


@app.get("/devices/{device_id}/readings")
def readings_in_range(
    device_id: str,
    start: datetime = Query(..., description="ISO-8601 UTC start of range (inclusive)"),
    end: datetime = Query(..., description="ISO-8601 UTC end of range (inclusive)"),
    metric: str | None = Query(None),
):
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    if end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)

    query = "SELECT * FROM readings WHERE device_id = %s AND recorded_at >= %s AND recorded_at <= %s"
    params = [device_id, start, end]
    if metric:
        query += " AND metric = %s"
        params.append(metric)
    query += " ORDER BY recorded_at ASC"

    with app.state.pool.connection() as conn:
        rows = conn.execute(query, params).fetchall()

    return [_row_to_json(r) for r in rows]

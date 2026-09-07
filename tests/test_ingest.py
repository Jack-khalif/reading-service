def reading(reading_id, metric="battery_percent", value=38, recorded_at="2026-09-07T09:15:00Z", device_id="PUMP-014"):
    return {
        "device_id": device_id,
        "reading_id": reading_id,
        "metric": metric,
        "value": value,
        "recorded_at": recorded_at,
    }


def test_ingest_then_fetch_latest(client):
    client.post("/readings", json=reading("r1"))
    resp = client.get("/devices/PUMP-014/metrics/battery_percent/latest")
    assert resp.status_code == 200
    body = resp.json()
    assert body["reading_id"] == "r1"
    assert body["value"] == 38


def test_latest_is_by_recorded_at_not_arrival_order(client):
    """
    A reading recorded at 09:15 arrives BEFORE one recorded at 09:20 is sent,
    but here we simulate the realistic case: the 09:20 one is recorded later
    but we still need 'latest' to reflect recorded_at, not insertion order.
    """
    client.post("/readings", json=reading("r1", recorded_at="2026-09-07T09:15:00Z", value=38))
    client.post("/readings", json=reading("r2", recorded_at="2026-09-07T09:20:00Z", value=35))

    latest = client.get("/devices/PUMP-014/metrics/battery_percent/latest").json()
    assert latest["reading_id"] == "r2"
    assert latest["value"] == 35


def test_out_of_order_arrival_still_resolves_correctly(client):
    """
    The device that recorded 09:20 arrives FIRST (network delay meant the
    09:15 one queued behind it). Latest must still be 09:20 by recorded_at,
    regardless of the order we received them in.
    """
    client.post("/readings", json=reading("r2", recorded_at="2026-09-07T09:20:00Z", value=35))
    client.post("/readings", json=reading("r1", recorded_at="2026-09-07T09:15:00Z", value=38))

    latest = client.get("/devices/PUMP-014/metrics/battery_percent/latest").json()
    assert latest["reading_id"] == "r2"
    assert latest["value"] == 35


def test_time_range_query_returns_ordered_subset(client):
    for i, ts in enumerate(["09:00", "09:05", "09:10", "09:15", "09:20"]):
        client.post("/readings", json=reading(f"r{i}", recorded_at=f"2026-09-07T{ts}:00Z", value=i))

    resp = client.get(
        "/devices/PUMP-014/readings",
        params={"start": "2026-09-07T09:05:00Z", "end": "2026-09-07T09:15:00Z"},
    )
    body = resp.json()
    assert [r["reading_id"] for r in body] == ["r1", "r2", "r3"]
    # must be ordered by recorded_at ascending
    assert [r["recorded_at"] for r in body] == sorted(r["recorded_at"] for r in body)


def test_latest_returns_404_when_no_data(client):
    resp = client.get("/devices/UNKNOWN/metrics/battery_percent/latest")
    assert resp.status_code == 404

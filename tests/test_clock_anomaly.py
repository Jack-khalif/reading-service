from datetime import datetime, timedelta, timezone

from tests.test_ingest import reading


def test_future_clock_reading_is_excluded_from_latest(client):
    good = reading("good-1", value=50, recorded_at="2026-09-07T09:00:00Z")
    far_future = (datetime.now(timezone.utc) + timedelta(days=3)).isoformat()
    bad = reading("bad-clock-1", value=99, recorded_at=far_future)

    client.post("/readings", json=good)
    client.post("/readings", json=bad)

    latest = client.get("/devices/PUMP-014/metrics/battery_percent/latest").json()
    # The wildly-future reading should NOT be allowed to win "latest",
    # even though its recorded_at is technically later.
    assert latest["reading_id"] == "good-1"


def test_all_anomalous_readings_still_returned_with_warning(client):
    far_future = (datetime.now(timezone.utc) + timedelta(days=3)).isoformat()
    only_bad = reading("only-bad", value=1, recorded_at=far_future)
    client.post("/readings", json=only_bad)

    resp = client.get("/devices/PUMP-014/metrics/battery_percent/latest")
    assert resp.status_code == 200
    body = resp.json()
    assert body["reading_id"] == "only-bad"
    assert "warning" in body

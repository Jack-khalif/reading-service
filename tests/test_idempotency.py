from tests.test_ingest import reading


def test_duplicate_reading_id_is_stored_once(client):
    r = reading("dup-1", value=38)
    client.post("/readings", json=r)
    client.post("/readings", json=r)  # re-sent, e.g. device retried after a timeout

    resp = client.get(
        "/devices/PUMP-014/readings",
        params={"start": "2026-09-07T00:00:00Z", "end": "2026-09-08T00:00:00Z"},
    )
    matching = [x for x in resp.json() if x["reading_id"] == "dup-1"]
    assert len(matching) == 1


def test_second_post_of_same_reading_reports_duplicate(client):
    r = reading("dup-2")
    first = client.post("/readings", json=r)
    second = client.post("/readings", json=r)

    assert first.status_code == 201
    assert first.json()["status"] == "created"
    assert second.status_code == 200
    assert second.json()["status"] == "duplicate"

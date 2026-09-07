"""
Two devices (or a retrying device) can send the SAME reading_id at almost
the same instant -- e.g. a flaky Wi-Fi connection causes a client-side
retry that races the original request.

This test fires the same reading twice, concurrently, and asserts that
the service handles it cleanly: both requests get a 2xx response, and
exactly one row ends up stored.

KNOWN ISSUE (see README "Flaky test" section): the current implementation
in app/main.py checks "does this reading_id exist?" and then, if not,
inserts it. Under concurrency this is a check-then-act race: both
requests can pass the check before either has inserted, and the second
INSERT then fails on the reading_id PRIMARY KEY constraint, raising an
unhandled IntegrityError -> 500. This test is intermittently flaky as a
direct result of that real race -- it is not a flaky test because of bad
test design, it is a flaky test because it is honestly reporting a race
that exists in the code.
"""
import threading

from tests.test_ingest import reading


def test_concurrent_duplicate_submission_is_handled_cleanly(client):
    r = reading("race-1", value=42)
    results = []

    def send():
        results.append(client.post("/readings", json=r))

    threads = [threading.Thread(target=send) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    statuses = sorted(resp.status_code for resp in results)
    assert all(s in (200, 201) for s in statuses), f"expected only 200/201, got {statuses}"

    check = client.get(
        "/devices/PUMP-014/readings",
        params={"start": "2026-09-07T00:00:00Z", "end": "2026-09-08T00:00:00Z"},
    )
    matching = [x for x in check.json() if x["reading_id"] == "race-1"]
    assert len(matching) == 1

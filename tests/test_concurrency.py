"""
Two devices (or a retrying device) can send the SAME reading_id at almost
the same instant -- e.g. a flaky Wi-Fi connection causes a client-side
retry that races the original request.

This test fires the same reading twice, concurrently, and asserts that
the service handles it cleanly: both requests get a 2xx response, and
exactly one row ends up stored.

FIXED (see README "Flaky test" section for the story): this test used to
be intermittently flaky, because the ingest endpoint used to check "does
this reading_id exist?" and then insert -- a check-then-act race where
both requests could pass the check before either had inserted, and the
second INSERT would then fail on the reading_id PRIMARY KEY constraint
with an unhandled IntegrityError -> 500. Fixed by switching to an atomic
INSERT OR IGNORE, so SQLite itself makes the uniqueness decision inside
one statement instead of the app making it across two. Verified stable
across 30 repeated runs at low concurrency and 15 at high concurrency
after the fix (see git history / README for numbers).
"""
import threading

from tests.test_ingest import reading


def test_concurrent_duplicate_submission_is_handled_cleanly(client):
    r = reading("race-1", value=42)
    results = []

    def send():
        results.append(client.post("/readings", json=r))

    threads = [threading.Thread(target=send) for _ in range(8)]
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

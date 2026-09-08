# Device Reading Service

A small service for ingesting device readings from hospital equipment over
unreliable Wi-Fi, and answering:
- the latest reading for a given device + metric, and
- the readings for a device over a time range.

## Running it

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Then:

```bash
curl -X POST localhost:8000/readings -H "Content-Type: application/json" -d '{
  "device_id": "PUMP-014",
  "reading_id": "a3f9c1",
  "metric": "battery_percent",
  "value": 38,
  "recorded_at": "2026-09-07T09:15:00Z"
}'

curl localhost:8000/devices/PUMP-014/metrics/battery_percent/latest

curl "localhost:8000/devices/PUMP-014/readings?start=2026-09-07T00:00:00Z&end=2026-09-08T00:00:00Z"
```

## Running the tests

```bash
python -m pytest -v
```

## Design decisions

**Storage.** SQLite, `reading_id` as the PRIMARY KEY. This isn't just "a
database" — the primary key is what actually gives us idempotency. We don't
maintain a separate "seen reading ids" set in application memory; SQLite's
own constraint is the source of truth for "have we stored this reading
already."

**recorded_at vs arrived_at.** These are stored as separate columns and
never conflated. Every "latest" or "range" query sorts and filters by
`recorded_at` — never by insertion order or `arrived_at` — because the spec
is explicit that latest means latest *by when it happened*, not by when we
heard about it. `arrived_at` is kept because it's still useful operationally
(e.g. to notice a device that's gone quiet), even though no endpoint here
queries by it.

**Idempotency (resent readings).** Ingest uses `INSERT OR IGNORE` on
`reading_id`. If the row already exists, the insert is a no-op and the
endpoint reports `{"status": "duplicate"}` with a 200. This has to be
*atomic* — see "The flaky test" below for what went wrong with the first
version of this.

**Out-of-order arrival.** No special handling is needed beyond correct
sorting, because we never rely on insertion order for anything. A reading
recorded at 09:15 that arrives after one recorded at 09:20 is simply another
row; the `ORDER BY recorded_at` in every query puts it in the right place
regardless of when it showed up.

**Clock skew / future timestamps.** A reading is flagged `clock_anomaly` at
insert time if its `recorded_at` is more than 2 minutes ahead of our
server's clock when we received it (small tolerance for normal drift and
network latency). Clock-anomalous readings are:
- still stored (we don't want to silently lose data from a device that's
  just fine but has a bad clock),
- excluded from "latest" by default, so one broken-clock device can't
  permanently poison what "latest" means for that device/metric,
- returned anyway, with a `"warning"` field, if *every* reading we have for
  that device/metric happens to be anomalous — so callers get an honest
  answer instead of a false "no data" 404.

This is a judgment call, not the only reasonable one. An alternative would
be to reject clearly-future readings outright at ingest time; I chose to
keep them and flag them instead, since a monitoring/audit context generally
benefits more from "we saw this, but flagged it" than from silently
dropping data.

## What I did not do, and why (scope discipline)

- **No authentication.** Explicitly out of scope per the brief.
- **No handling of a device's clock being *wrong in the past*** (e.g.
  permanently 3 hours behind) — that's much harder to distinguish from a
  legitimately late-arriving-but-correctly-timestamped reading, and the
  brief's examples are specifically about *future* clock errors. I'd want
  to know more about real device behavior before guessing at a heuristic
  here.
- **No retry/backoff logic on the device side** — devices are simulated as
  simple POST senders; the resend/out-of-order/duplicate behaviors are
  handled entirely server-side, which is what the spec asks for.
- **No pagination on the range-query endpoint.** For a real deployment with
  months of data per device this would matter; for the scope here (and the
  time box), I judged it not worth the complexity.
- **No database migrations tooling** — schema is created directly via
  `CREATE TABLE IF NOT EXISTS` on startup, which is fine for a single
  SQLite file with one table, but is a corner I'd cut differently in a
  service that expected to evolve its schema over time.

## The flaky test

**The scenario.** Devices on bad hospital Wi-Fi can retry a send if they
don't get a timely response, so the same `reading_id` can arrive twice at
almost the same instant — a genuine concurrent duplicate, not a
sequential one.

**What I wrote first** (`app/main.py`, first version): ingest checked
`SELECT ... WHERE reading_id = ?`, and if nothing came back, ran a
separate `INSERT`. This reads fine and passes every *sequential* test.

**Why it's wrong.** Under concurrency this is a check-then-act race: two
requests for the same `reading_id` can both run their `SELECT` and both
see "nothing here yet" before either has run its `INSERT`. The first
`INSERT` succeeds; the second then hits the `reading_id` PRIMARY KEY
constraint and raises an unhandled `sqlite3.IntegrityError`, which
FastAPI turns into an unexpected 500 — the request that should have been
a harmless "yes, we already have that one" instead crashes.

**The test that caught it:** `tests/test_concurrency.py`. It fires the
same reading twice from two threads at once and asserts every response is
a 2xx and exactly one row ends up stored. Against the naive
implementation this test is genuinely intermittent — not deliberately
sabotaged to fail, just honestly reporting a real race — because whether
the two threads' SELECTs happen to land in the same narrow window depends
on OS thread scheduling. Run locally 20 times against the naive version:
roughly 1 in 20 runs failed. That's the signature of a real race, not a
badly-written test: a badly-written flaky test (e.g. one that depends on
wall-clock sleep timing, or on dict ordering) fails for reasons that have
nothing to do with the code under test. This one fails for exactly the
reason the code is wrong.

**The fix:** replace the check-then-insert with a single atomic
`INSERT OR IGNORE`, and use SQLite's `changes()` to find out whether this
particular call was the one that inserted. Now there's only one statement
making the uniqueness decision, so there's no window for a second request
to slip into. Re-run 30 times at 2 concurrent requests and 15 times at 8
concurrent requests after the fix: 0 failures.

**The two commits to look at:**
1. `Add concurrency test for duplicate submission -- intermittently failing`
2. `Fix duplicate-ingestion race: atomic INSERT OR IGNORE instead of check-then-insert`


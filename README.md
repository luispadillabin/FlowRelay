# FlowRelay

A local webhook event workbench built with Python, SQLite, and vanilla JavaScript.
Receive fictional events, validate JSON, prevent duplicate processing, simulate failures,
and inspect retries through a browser dashboard.

## Why this project exists

Event-driven integrations must handle repeated requests and temporary failures.
FlowRelay makes these behaviors visible in a small, inspectable codebase. It is a
portfolio and learning project, not a production webhook gateway.

## Run

Requires Python 3.10 or newer. No pip packages or frontend build tools are needed.

```sh
python server.py
```

Open **http://127.0.0.1:8000**. On Windows, use `py server.py` if `python` is unavailable.
Keep the terminal open; press Ctrl+C to stop. For a different port, use
`python server.py --port 8080` and open http://127.0.0.1:8080.

**Do not double-click static/index.html.** The UI needs the API server.
GitHub stores this repository; GitHub Pages cannot host its Python API.

## Try the full workflow

1. Click **Success**, then **Receive event**, then **Process next due event**.
2. Resend the same JSON: it is acknowledged without creating another event.
3. Change its summary without changing its ID: the API returns a conflict.
4. Click **Retry once**, receive it, and process it. Wait two seconds, then process again.
5. Click **Exhaust retries**, receive and process it. Wait two seconds for attempt 2,
   then four more seconds for attempt 3. Its final state is `dead_letter`.
6. Click an event ID to inspect the payload and ordered attempt history.
7. Restart the server: events remain in `flowrelay.db`.

Processing is **manual**: time passing makes a retry eligible but does not execute it.
Refresh updates the table; processing also refreshes it automatically.

## API

| Method | Path | Behavior |
| --- | --- | --- |
| GET | `/api/health` | Health and simulation mode |
| GET | `/api/events` | Latest 200 events, total count, counts by status |
| GET | `/api/events/{event_id}` | Event plus attempt history; 404 if missing |
| POST | `/api/events` | Receive an event; 201 new, 200 identical duplicate, 409 conflicting ID |
| POST | `/api/process` | Process one due event; send `{}`; returns null if nothing is due |

POST requests require `Content-Type: application/json`. Bodies are capped at 16 KiB.
Invalid data returns 400, unsupported content types 415, oversized bodies 413.
Unknown paths return 404. Responses use JSON.

```json
{
  "event_id": "demo-001",
  "event_type": "ticket.created",
  "payload": {
    "ticket_id": "DEMO-1042",
    "priority": "high",
    "summary": "Fictional account access request",
    "fail_until": 1
  }
}
```

`event_id` and `event_type` allow 1–80 ASCII letters, digits, dots, hyphens or
underscores. Payload is an object with only the four optional fields above.
Text values are limited to 200 characters. `fail_until` is an integer 0–10;
it simulates failures through that attempt number. At most three attempts run.
Unknown fields, duplicate JSON keys, and non-finite JSON numbers are rejected.
The example with `fail_until: 1` fails once and succeeds on its second attempt.

## Architecture and guarantees

- `server.py`: loopback HTTP API and static assets.
- `relay.py`: input validation, SQLite transactions, queue state machine.
- `static/`: dashboard; DOM text is inserted with textContent, not HTML injection.
- `tests/`: isolated queue and HTTP integration tests using temporary databases.

States: `pending` → `succeeded` or `retry_wait`; retry attempts can end in
`succeeded`, another `retry_wait`, or `dead_letter`. There is no automatic replay.
Retries use 2- and 4-second delays. The inspector stores Unix UTC timestamps;
the table displays retry time in the browser's local timezone.

A SQLite write transaction covers each submission or simulated processing step.
The primary key enforces unique event IDs, and canonical JSON makes payload key
order irrelevant for duplicate detection. The same ID with changed data returns
409, even after completion. Processing and its history are committed together.
Concurrent local workers cannot process the same event twice in this simulation.
This does **not** establish exactly-once delivery to an external service.

## Tests

```sh
python -m unittest discover -s tests -v
```

The 12 tests cover validation, duplicate/conflict behavior, success, retry-time
boundaries, dead-letter history, restart persistence, concurrent submissions and
processing, HTTP flow, origin restrictions, malformed JSON, size/content checks,
and asset routes. GitHub Actions runs them on Python 3.10 and 3.12.

### Local verification — November 12, 2026

All 12 tests passed on Windows in 3.238 seconds.
SQLite connections now close after each operation, and the previous
`WinError 32` did not recur during this test run.

### Browser verification — November 13, 2026

Manually verified:
- Successful processing on the first attempt.
- Duplicate acknowledgement (200) without creating another event.
- Conflict rejection (409) for changed data using the same event ID.
- Retry recovery on the second attempt.
- Dead-letter status after three failed attempts.
- Attempt history showing each processing outcome.
- Stored events remaining available after a server restart.

## Limits and next steps

The server binds only to 127.0.0.1. It has no user accounts, authentication,
webhook signature verification, automatic scheduler, real delivery, retention
policy, or production deployment configuration. Browser cross-origin writes are
rejected, and it makes no outbound network requests. Use fictional data only.
The standard-library HTTP server is for local development; do not expose it
publicly. Schema creation supports a new database; schema migrations are not yet
implemented. Database size is not capped; deleting the local database resets it.

Future work with useful acceptance criteria:

- **Event pagination:** fetch beyond the latest 200; test boundaries and stable ordering.
- **Dead-letter replay:** explicit action, preserve history and record replay reasons.
- **Background worker:** graceful shutdown and tests ensuring due events run once.
- **Signed webhooks:** verify signatures and reject expired requests with fixtures.
- **UI automation tests:** cover keyboard use, scenarios, conflict messages, mobile layout.

## Authorship and license

Personal portfolio project by Luis Padilla, developed with AI assistance.
The code, documentation, and tests were generated with assistance and should be
studied and independently reviewed before extending or deploying.
This project does not claim real customers, production usage, or a company affiliation.
Released under the MIT License; see LICENSE.

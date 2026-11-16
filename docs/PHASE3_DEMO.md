# Phase 3: real local incident demonstration

Run from `/path/to/OpsGuard-AI`. Install dependencies as in SETUP_GUIDE first. This demo uses a newly created disposable database; it never clears or changes `backend/opsguard.db`.

## Prepare

```sh
python3 scripts/prepare-incident-demo.py
```

The script prints an exact `source .../environment.sh` command and a name such as `phase3-<12 hex digits>`. Use that printed command in BOTH the backend and payment-service terminals. The private file contains matching server-only credentials and an isolated DATABASE_URL. Do not paste credentials into browser configuration, logs, or Git.

## Start processes

Terminal 1, project root:

```sh
# Run the printed source command first.
cd backend
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Terminal 2, project root:

```sh
# Run the SAME printed source command first.
cd services
npm run start:payment
```

Terminal 3, project root:

```sh
cd frontend
npm run dev
# If the local Turbopack permission error occurs: npm run dev -- --webpack
```

Open http://127.0.0.1:3000/incidents. The new demo initially shows no incidents. Open /services for actual observed health. User/order services will be unknown/degraded/unavailable if they are not running; that is expected. Optionally start them in separate terminals with `npm run start:user` and `npm run start:order` from services/.

## Trigger and inspect

Terminal 4, project root:

```sh
curl -i -X POST http://127.0.0.1:3003/simulate/payment-failure -H 'Content-Type: application/json' -d '{}'
curl -s http://127.0.0.1:8000/api/incidents
curl -s http://127.0.0.1:8000/api/incidents/summary
```

Expected service response: HTTP 502, PaymentFailure, message `Simulated payment processor rejection`, and a request_id. The service terminal writes JSON request and incident records. FastAPI receives the authenticated event. `/api/incidents` returns one OPEN payment-service record with occurrence_count 1. Open its details in the dashboard for timestamps, stack, request ID and event history. Allow a few seconds for publication and five-second dashboard polling.

Repeat the SAME curl failure request within 300 seconds. The same incident now has occurrence_count 2 and two distinct events. Re-delivering an already accepted event_id never increments the count. The incident stays OPEN until explicitly managed.

To inspect SQLite directly, first source the same environment file in this terminal, then:

```sh
backend/.venv/bin/python - <<'PYCODE'
import os, sqlite3
from sqlalchemy.engine import make_url
path = make_url(os.environ['DATABASE_URL']).database
with sqlite3.connect(path) as db:
    print(db.execute('SELECT id, service_name, status, occurrence_count FROM incidents').fetchall())
    print(db.execute('SELECT event_id, request_id, http_status FROM incident_events').fetchall())
PYCODE
```

Stop/restart FastAPI with the same sourced environment and working directory. Records remain. Stop each server with Control-C. Do not share the demo or bind it publicly.

## Explicit local status management

Disabled by default. In the backend terminal only, set `ENABLE_INCIDENT_MANAGEMENT=true`, `ENVIRONMENT=development` and a separate nonempty `INCIDENT_MANAGEMENT_TOKEN`, then restart. Use a loopback API request with `Authorization: Bearer <management token>`:

```text
PATCH /api/incidents/<actual-id>/status
{"status":"INVESTIGATING"}
```

Supported transitions: OPEN → INVESTIGATING; INVESTIGATING → RESOLVED or OPEN; RESOLVED → OPEN. Repeating the current status is idempotent. OPEN → RESOLVED returns 409. There is no public deletion endpoint and no frontend storage of management credentials.

## Clear only this disposable database

Stop its FastAPI process first. Use the exact demo name printed during preparation:

```sh
python3 scripts/clear-incident-demo.py phase3-<actual-12-hex-digits>
```

The script requires typing `DELETE <exact-name>` before touching data. It verifies the name, directory and disposable marker; rejects symbolic links; removes only that demo's SQLite database/journal files; preserves environment configuration and unrelated databases. A wrong confirmation cancels. Restarting FastAPI recreates empty tables. There is no general-purpose database deletion command.

## Automated real-process check

```sh
backend/.venv/bin/python scripts/check-incident-pipeline.py
```

This starts actual FastAPI and Node processes on temporary loopback ports, generates a temporary token/database, and runs the actual React list/details/service components in jsdom with real HTTP fetches. It checks automatic list/occurrence updates, event evidence, SQLite rows, actual service health, safe logs, and restart persistence. No network responses are mocked. Only runner-owned child processes are stopped. The private disposable evidence directory, SQLite database and sanitized service log are preserved by default; its exact path is printed. `--discard-evidence` is an explicit opt-in cleanup option and must not be used without owner authorization. The runner also checks three-service health, payment outage/recovery, dashboard metrics and analytics event counts. This is a DOM integration test, not screenshot/layout or full browser navigation verification.

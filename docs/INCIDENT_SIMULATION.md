# Phase 2 incident simulation

## Start and stop

Requires Node.js 22.18+ and npm, or Docker Engine/Desktop with Compose v2. Use the existing frontend and backend commands independently; this Compose stack contains only the three simulated services.

```sh
cd services
npm ci
npm test
# Default: fault routes disabled.
docker compose config
docker compose up --build -d --wait
docker compose ps
curl http://127.0.0.1:3001/health
curl http://127.0.0.1:3002/health
curl http://127.0.0.1:3003/health
docker compose logs --follow --tail=50
# Stop only this stack; do not remove volumes:
docker compose down
```

Enable controlled faults explicitly for a local session:

```sh
NODE_ENV=development ENABLE_FAULT_INJECTION=true docker compose up --build -d --wait
curl -X POST http://127.0.0.1:3003/simulate/database-failure -H 'Content-Type: application/json' -d '{}'
# Restore disabled defaults by recreating the services:
NODE_ENV=production ENABLE_FAULT_INJECTION=false docker compose up -d --force-recreate --wait
```

Compose publishes ports only on 127.0.0.1. Never expose this development stack through public forwarding. Fault routes return 403 unless both settings match exactly. Entry points refuse startup if faults are enabled outside development. These are development configuration controls, not authentication.

Without Docker, use separate terminals from `services/`:

```sh
NODE_ENV=development ENABLE_FAULT_INJECTION=true npm run start:user
NODE_ENV=development ENABLE_FAULT_INJECTION=true USER_SERVICE_URL=http://127.0.0.1:3001 npm run start:order
NODE_ENV=development ENABLE_FAULT_INJECTION=true ORDER_SERVICE_URL=http://127.0.0.1:3002 npm run start:payment
```

Stop Node processes with Control-C. PORT and HOST are configurable; Node defaults to loopback. Each entry point drains active connections on SIGTERM/SIGINT, with a five-second shutdown bound. User and order lookup dependencies are optional for isolated Node testing, enabled by URL environment variables, and always enabled in Compose.

## Endpoints and response format

| Service | Port       | Method and path          | Behavior                                                  |
| ------- | ---------- | ------------------------ | --------------------------------------------------------- |
| All     | respective | GET /health              | 200 liveness; service name and healthy status             |
| User    | 3001       | POST /users              | 201 simulated registration; name and valid email required |
| User    | 3001       | GET /users               | 200 registered users                                      |
| User    | 3001       | GET /users/:id           | 200 user, or 404                                          |
| Order   | 3002       | POST /orders             | 201 order; user_id and amount_cents required              |
| Order   | 3002       | GET /orders/:id          | 200 order, or 404                                         |
| Payment | 3003       | POST /payments           | 201 processed payment; order_id and amount_cents required |
| Payment | 3003       | GET /payments/:id        | 200 payment and status, or 404                            |
| All     | respective | POST /simulate/:scenario | Explicitly gated controlled fault                         |

Successful envelopes: `{"success":true,"data":{...}}`; `/users` lists an array. Errors: `{"success":false,"error":{"type":"ValidationError","message":"..."},"request_id":"<uuid>"}`. Every response carries X-Request-ID. Unknown endpoints return 404. Malformed JSON returns 400, bodies above 16 KiB return 413. Registration rejects duplicate normalized email with 409. Record IDs allow 1–64 letters, digits or hyphens. Amounts are integer cents from 1 through 100,000,000. Payment adds a rounded 2% simulated fee.

User lookup rejects an unknown user with 422; payment rejects an unknown order or mismatched amount with 422. Unavailable/non-successful dependencies return 503. Lookups have a one-second deadline. Health is local process liveness and remains healthy during dependency failures.

## Example user → order → payment flow

```sh
curl -s -X POST http://127.0.0.1:3001/users -H 'Content-Type: application/json' -d '{"name":"Ada","email":"ada@example.test"}'
# Copy data.id from the result as USER_ID:
curl -s -X POST http://127.0.0.1:3002/orders -H 'Content-Type: application/json' -d '{"user_id":"USER_ID","amount_cents":10000}'
# Copy the returned order data.id as ORDER_ID:
curl -s -X POST http://127.0.0.1:3003/payments -H 'Content-Type: application/json' -d '{"order_id":"ORDER_ID","amount_cents":10000}'
# Read the returned payment data.id:
curl http://127.0.0.1:3003/payments/PAYMENT_ID
```

The final creation returns 201 with id, order_id, amount_cents 10000, total_cents 10200 and status processed. The placeholders above must be replaced with the IDs actually returned; no seed users or orders are assumed. Data resets on restart. A process permits up to 1,000 records and returns 503 on further creation.

A real missing-amount request also works without fault injection:

```sh
curl -X POST http://127.0.0.1:3003/payments -H 'Content-Type: application/json' -d '{"order_id":"order-1"}'
```

Expected: 400 ValidationError, message `Positive integer amount_cents is required`.

## Reproducible scenarios

Each shared scenario below is available on all three services. Use `POST /simulate/NAME` with `{}`. After each request, `GET /health` must still return 200. No scenario changes service-wide business behavior or leaves an active background operation.

| NAME                   | Expected HTTP / error       | Operation                                                                |
| ---------------------- | --------------------------- | ------------------------------------------------------------------------ |
| missing-payment-amount | 400 ValidationError         | Runs real payment validation with absent amount                          |
| null-access            | 500 InternalError           | Executes a null property access; sanitized actual stack retained         |
| database-failure       | 503 DatabaseConnectionError | Request-scoped simulated connection refusal; no real DB modified         |
| request-timeout        | 504 RequestTimeout          | Aborts a 500ms timer at a 30ms deadline                                  |
| invalid-configuration  | 500 ConfigurationError      | Validates an intentionally invalid request-local fee setting             |
| calculation-regression | 500 CalculationRegression   | Detects fee subtraction against the expected addition invariant          |
| slow-downstream        | 503 SlowDependency          | Waits 60ms and reports exceeding a simulated 50ms budget                 |
| repeated-500           | 500 RepeatedServerError     | One error per caller request; no server-generated retry loop             |
| faulty-commit          | 500 FaultyCommitRegression  | Executes regression-fee-v1 fixture; detects incorrect total              |
| bounded-memory         | 200 success                 | Allocates 4 MiB for 20ms; returns allocated_bytes 4194304 and checksum 2 |

The faulty-commit scenario uses a versioned faulty source fixture in `services/fixtures/`. It creates no Git commits and never edits the working tree. Database and slow dependency scenarios are deliberate simulations; no actual database outage or external network attack occurs. Concurrent memory requests return 429 SimulationBusy; there is at most one 4 MiB allocation per process. There are no infinite loops or unbounded allocation parameters.

Service-specific controls:

| Service | POST path                        | Expected                 |
| ------- | -------------------------------- | ------------------------ |
| User    | /simulate/authentication-error   | 401 AuthenticationError  |
| Order   | /simulate/order-processing-error | 500 OrderProcessingError |
| Payment | /simulate/payment-failure        | 502 PaymentFailure       |

Repeated error example, bounded by three caller requests:

```sh
for attempt in 1 2 3; do
  curl -X POST http://127.0.0.1:3002/simulate/repeated-500 -H 'Content-Type: application/json' -d '{}'
done
```

## Evidence and limits

Each completed request writes a structured JSON line to stdout containing timestamp, service_name, level, request_id, method, path (route template), status_code, duration_ms, error_type, error_message and stack_trace. Nullable error fields are present on successes. Request bodies, headers, query strings, raw user IDs, email addresses, passwords and tokens are not logged. Server-created IDs avoid trusting caller-supplied request IDs.

Error completions additionally publish the [incident event contract](INCIDENT_EVENT_CONTRACT.md) as an `event: "incident"` JSON log. Filter by request_id to connect the two records. `docker compose logs payment-service --tail=50` displays evidence. Docker's json-file logs rotate at 5 MiB with two files per container. Node-only runs print the same JSON to the terminal.

Containers use non-root node, read-only filesystems, dropped capabilities, no privileged mode or host socket, 128 MiB memory, 0.5 CPU and 64 process limits. Restart is on-failure with three retries. Health checks run every ten seconds; unhealthy status alone does not restart a running container. Compose waits for user health before order, and order before payment. No production deployment is included.

Automated tests exercise each service independently, invalid inputs, fault routes and gates, recovery, evidence, publisher failures/timeouts/concurrency, event field constraints and the actual cross-service HTTP flow. Docker must still be installed to verify image builds and container health on the target machine.


## Phase 3 pipeline integration

Configure INCIDENT_INGESTION_URL and the matching INCIDENT_WEBHOOK_TOKEN to send the same v1 events to FastAPI, in addition to stdout. Direct Node processes need exported variables; Compose accepts the same variables through environment substitution. Leave the URL empty for stdout-only operation. Credentials never belong in NEXT_PUBLIC configuration.

See [the complete macOS demonstration](PHASE3_DEMO.md) for a real payment failure → SQLite → dashboard flow, repeated occurrence counting, backend restart, and explicitly confirmed cleanup of only marked disposable data. [Setup](SETUP_GUIDE.md) documents host/container URLs and [the contract](INCIDENT_EVENT_CONTRACT.md) documents authentication, limits and bounded retries. There is no Docker requirement for this flow. Docker builds/health remain separately unverified.

Phase 3 analytics shows stored incident events; no fabricated traffic, error-rate or uptime measurements are shown. Health reflects actual polling of the three services. AI investigation and historical semantic indexing remain planned.

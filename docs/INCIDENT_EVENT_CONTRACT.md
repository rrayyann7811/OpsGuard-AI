# Incident event contract v1 — Phase 3 consumer

The Phase 2 envelope and [`services/incident-event.schema.json`](../services/incident-event.schema.json) are unchanged. Producers are validated against that actual JSON Schema with Ajv/formats tests; FastAPI validates the same fields with Pydantic. No field is silently dropped.

| Required field | Meaning |
| --- | --- |
| event_id | UUID v4, unique delivery identity; retries reuse it |
| service_name | user-service, order-service, payment-service |
| timestamp | Timezone-aware source timestamp, stored/canonicalized as UTC |
| severity | warning or error, preserved on event evidence |
| error_type | Nonblank classification, maximum 128 characters |
| error_message | Nonblank safe description, maximum 4096 characters |
| stack_trace | String up to 16384 characters, or null |
| http_status | Integer 400–599 |
| request_id | Server-generated UUID v4 for request correlation |
| endpoint | Route template starting with /, maximum 512 characters |
| duration_ms | Finite nonnegative number, at most 86400000 |

FastAPI operational limits supplement the original schema: request body at most 32 KiB, bounded strings/duration, nonblank classification/message, UUID v4 identities. Current producers meet them. Extras and malformed input return 422 without echoing submitted values; oversized bodies return 413. HTTP authentication uses `Authorization: Bearer <INCIDENT_WEBHOOK_TOKEN>`. Empty backend token disables ingestion with 503; missing/wrong credentials return 401.

Before storage, key/value credentials (including quoted values), bearer values, URL userinfo and email addresses are redacted from text; query strings/fragments are removed from endpoints. Do not submit credentials or raw request bodies. Redaction is defense in depth, not a guarantee for every possible secret syntax. Original non-sensitive messages/frames and all event fields are retained in the event metadata JSON. UTC timestamp formatting may be canonicalized without changing the instant.

Incident severity maps warning → medium, error → high, with 503/504 → critical. Source severity remains intact in each event. A successful webhook delivery never resolves an incident.

## Publication

`createApp(service, { publish })` retains the Phase 2 injection point and stdout event adapter. Setting INCIDENT_INGESTION_URL enables an additional HTTP transport; INCIDENT_WEBHOOK_TOKEN is required. Without a URL, services still generate local JSON event logs. A safe PublicationFailure log indicates unsuccessful remote delivery.

The existing createPublisher bound is reused: at most 16 pending operations, a two-second service-level publication deadline, no durable queue. Each HTTP operation has at most three attempts, a 500ms per-attempt timeout, and 50/100ms bounded backoff. Retries apply to network errors, 429 and 5xx. Other 4xx responses stop immediately. Redirects are rejected to avoid forwarding credentials. Each retry uses the same event_id and body. Timeout/transport errors never change the original service response or crash the process. An uncooperative transport retains its slot until it settles. Saturation drops new events; delivery is best effort, with no recovery of events lost during prolonged outages or process termination.

For direct macOS processes use `http://127.0.0.1:8000/api/incidents/events`. For Docker Desktop against FastAPI on the Mac, configure `http://host.docker.internal:8000/api/incidents/events` and ensure the host API bind/firewall permits the container route. For a backend on a Compose network, configure its actual DNS name. There is no hardcoded container hostname and no backend container is added in this phase.

## Deduplication

FastAPI generates SHA-256 over service, lowercased error type, normalized message, endpoint, HTTP status and first relevant stack frame. Messages collapse whitespace and replace UUIDs; ordinary numeric evidence remains significant. Stack checkout prefixes and line/column numbers are excluded, and node internal/dependency frames are ignored. This groups related call-site errors while preserving different services, operations and substantive evidence. Stack changes can intentionally split groups.

A configurable DEDUP_WINDOW_SECONDS (default 300, bounded 1–86400) uses the latest received event time. Only OPEN/INVESTIGATING incidents qualify. Source timestamps determine first_seen/last_seen through min/max and can arrive out of order. `last_received_at` tracks receipt separately from `updated_at` status changes. The initial incident preserves its first error evidence; each occurrence retains its own evidence in event history.

A unique event_id prevents reinsertions and count inflation, even if the incident is later resolved. The first accepted payload wins for a reused event ID. SQLite BEGIN IMMEDIATE serializes ingestion transactions; incident and event updates commit together. Matching events outside the window or after resolution create a new OPEN incident. Explicit reopening uses the restricted management API and never happens implicitly.

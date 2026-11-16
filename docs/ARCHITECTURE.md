# Current architecture — Phase 5 read-only investigation orchestration

```text
Persisted incident + authorized local start
 → SQLite investigation + lifecycle events (unique active incident)
 → sequential asynchronous worker
 → existing historical retrieval + approved source/Git evidence
 → sanitized evidence bundle → official Codex SDK adapter
 → mandatory containment/configuration/paid-authorization gate
 → strict attributed report validation → SQLite → polling investigations UI
```

The integration is implemented but **live verification is pending**. The host containment probe fails with SIGABRT; the adapter blocks model execution. No generated AI report or benchmark is represented as genuine Codex output. The separately verified surrounding integration uses actual service/RAG/source/Git/SQLite/React with a labeled test double.

New investigation/event tables are additive; existing incident tables and Qdrant data remain intact. Application collectors are read-only, bounded and path/command allowlisted. The inherited home-root Git repository is rejected. The model never receives access to the original repository. Paid starts require a dedicated local token, explicit boolean authorization, dedicated API key/model, enabled configuration and verified containment. Startup fails unfinished jobs rather than fabricating completion. No automatic patching, execution of proposed fixes or Phase 6 automation exists.

See [agent architecture](AGENT_ARCHITECTURE.md), [workflow/API/configuration](INVESTIGATION_WORKFLOW.md), and [evaluation limitations](AGENT_EVALUATION.md). Source/Git tool events and report provenance checks support inspection, but do not prove semantic correctness or causal reproduction. Existing incident monitoring and Phase 4 historical retrieval remain functional.

---

Earlier phase architecture below is historical; statements that Phase 5 is planned describe those earlier checkpoints.

# Current architecture — Phase 4 historical retrieval

```text
knowledge/data/incidents.json (24 synthetic, attributed sources)
 → validation/normalization/redaction → token-aware preparation
 → local pinned MiniLM CPU embeddings → dedicated Qdrant cosine index
 → actual similarity search + optional service/severity filters
 → FastAPI knowledge APIs → Next.js source search/details

SQLite operational incident → read-only error evidence → similar-history retrieval
```

Operational incident storage, lifecycle, ingestion and the three Express services retain Phase 3 behavior. No operational incident-management tables were duplicated in Qdrant or rewritten. Qdrant stores searchable historical document/chunk metadata and vectors; the curated JSON remains its source. SQLite remains operational truth. Search is retrieval, not an AI-generated root-cause conclusion.

New backend modules: knowledge_documents, knowledge_embeddings, knowledge_store, knowledge_api and knowledge_cli. APIs: GET /api/knowledge/status, GET /api/knowledge/incidents, GET /api/knowledge/incidents/{id}, POST /api/knowledge/search, POST /api/knowledge/similar/{operational-id}. Mutation is a local development CLI, with no reindex HTTP endpoint. Model/client initialization is lazy so unavailable optional ML dependencies do not break incident monitoring. Sync search runs in FastAPI's worker threads; within-process Qdrant/model operations are serialized.

The model is pinned to an immutable revision and outputs normalized 384-dimensional vectors. Existing collection geometry is checked, stable IDs/content hashes support idempotent upserts, and replaced chunks activate only after successful writes. No collection/storage deletion is implemented. Embedded persistent local Qdrant is a supported development mode, not a server; one process owns its path. A configured QDRANT_URL selects real server mode, unverified here. See [pipeline/configuration](RAG_PIPELINE.md) for precise indexing, failure and locking behavior.

Historical Knowledge now shows actual index/source/model information, explicit search/filter/loading/error states, cosine scores, synthetic source cards and full source dialogs. Operational incident details can request related historical evidence while retaining their status and evidence. The existing dark UI/shell, incident pages, metrics and services remain intact. No Codex agent, generation or Phase 5 action is implemented.

The reproducible [evaluation](RAG_EVALUATION.md) uses real vectors and the same 24 queries across semantic, metadata-filtered and hybrid experiments. No quality improvement was observed from the hybrid heuristic, so the public API/UI retains semantic-only ranking. Tests separately distinguish deterministic embedding doubles from genuine offline-model + persistent-Qdrant integration.

---

The following Phase 1–3 reports are historical and superseded where retrieval was previously described as planned.

# Current architecture — Phase 3

```text
Express user/order/payment failure
  → structured request + event stdout logs
  → bounded publisher / HTTP transport (server-only bearer authentication)
  → POST FastAPI /api/incidents/events
  → validation + redaction + signature + transactional deduplication
  → SQLite incidents + incident_events
  → incident list/detail/history/summary APIs
  → Next.js five-second polling → real dashboard and evidence dialogs

FastAPI lifespan task → concurrent bounded /health checks → /api/services → service cards
```

## Database

`Incident` stores UUID id, service/title, normalized severity, OPEN/INVESTIGATING/RESOLVED status, indexed signature, initial error/message/stack/endpoint/HTTP status, source first/last-seen, occurrence_count, created_at, updated_at and internal last_received_at. Status edits update updated_at without extending the event deduplication window. Status/count checks and service/severity/status/time/signature indexes constrain and support queries.

`IncidentEvent` stores integer primary key, globally unique event_id, indexed incident foreign key and request_id, source timestamp, error type/message/status/duration, and complete redacted event evidence in the metadata JSON column. UTC timestamps are stored as naive UTC in SQLite and serialized with a UTC offset. Event_id uniqueness protects retries; a SQLite write lock serializes event grouping/insertion. No history is deleted on startup. create_all is additive initial schema setup, not a migration system.

## API boundaries

| Method | Endpoint | Behavior |
| --- | --- | --- |
| POST | /api/incidents/events | Authenticated v1 event ingest; duplicate flag and incident |
| GET | /api/incidents | items/total/page/page_size; search, severity, status, service filters; last-seen descending |
| GET | /api/incidents/summary | active/critical/resolved/total, severity counts, latest 30 UTC days containing events |
| GET | /api/incidents/{id} | Incident evidence and lifecycle fields |
| GET | /api/incidents/{id}/events | Newest-first paginated immutable occurrence evidence |
| PATCH | /api/incidents/{id}/status | Explicit local development management; separate bearer token |
| GET | /api/services | Actual observed service states |
| GET | /api/health | Preserved Phase 1 SQLite SELECT 1 contract |

See [event contract](INCIDENT_EVENT_CONTRACT.md) for grouping and publication policy and [design decisions](PHASE3_DESIGN.md). List/event pagination defaults to 20 and is bounded to 100. Missing records return 404; malformed inputs 422; invalid status transitions 409; unsafe management requests 403. OPEN can move to INVESTIGATING; INVESTIGATING to RESOLVED or OPEN; RESOLVED explicitly to OPEN. A subsequent failure never silently resolves or reopens an old incident.

## Monitoring and frontend

One lifespan-owned async monitor polls the configured three service URLs concurrently with httpx. Initial state is Unknown. Successful valid service-specific health envelopes classify Healthy or latency-based Degraded; failed checks classify Degraded initially and Unavailable after three consecutive failures. Records expose availability, last attempt/success, latency, safe failure reason and consecutive failures. State resets to Unknown on API restart; no uptime history is claimed. Polling never blocks request handlers, and shutdown signals and awaits the task.

The existing shared shell, panel/table/card styles, dialog behavior, preferences and Phase 1 health provider are retained. MonitoringProvider owns shared summary and service polls. IncidentTable owns its paginated filtered poll, and an open detail owns detail/history polls. Each schedules its next request only after completion, aborts on cleanup and retries offline after ten seconds. Search is debounced. Overview, incidents, services and analytics use actual API data; legacy fixtures remain isolated for Phase 1 tests. Analytics counts stored events, not request/error rates. AI/RAG pages remain planned.

## Security and operational boundary

Webhook secrets are server-only; management is disabled by default, requires a separate secret and loopback development client. APIs are intended for local use and do not provide user authentication. Body reads are bounded to 32 KiB before parsing, validation errors omit submitted values, SQL uses bound expressions, and evidence is redacted before storage. Service logs avoid bodies/query strings and HTTP retries reject redirects. No deletion API is exposed. Demo cleanup accepts only marked disposable paths and requires typed confirmation.

Delivery is best effort, bounded and not durable; outages can lose events. SQLite single-host operation and one backend worker are the intended development setup. Production auth, retention, migrations, durable delivery and deployment are outside this phase. Docker configuration remains statically checked only; runtime verification is pending. Phase 4 RAG has not begun.

---

The following records the historical Phase 1/2 architecture; statements about planned ingestion describe those earlier phases, superseded above.

# Architecture

## Phase 1: implemented

```text
Browser
  │
  ├── Next.js App Router (127.0.0.1:3000)
  │     ├── Shared shell, navigation, reusable interface components
  │     ├── Labeled demonstration dataset → tables / service cards / analytics
  │     └── Browser local storage → workspace preferences
  │
  └── GET http://127.0.0.1:8000/api/health (direct browser fetch)
        └── FastAPI + Pydantic settings + local CORS policy
              └── SQLAlchemy → SQLite SELECT 1
```

Next.js renders shared layouts and statically generates the seven dashboard routes. Client components handle filters, dialogs, charts, preferences, and health requests. `src/lib/demo.ts` is the single source of demonstration records. Analytics count active/healthy/resolved records and calculate mean resolution duration from resolved records; traffic samples are an explicitly labeled independent series.

`HealthProvider` shares one health result across navigation, overview, and settings. Requests validate the response contract, time out after five seconds, poll every 30 seconds, and abort on cleanup. Manual checks show pending and success/offline feedback. The public API URL defaults to loopback and can be configured before build. CORS permits only explicitly configured origins; Phase 1 requires GET access only.

FastAPI exposes `/api/health`, `/docs`, `/redoc`, and `/openapi.json`. A failed SQLite query returns 503. Unexpected errors return a generic 500 body while details remain in server logs. SQLAlchemy's declarative base and session dependency provide a starting point for later domain models. No incident tables or migrations exist in this phase. A successful health check confirms database reachability, not readiness of future incident schemas.

## Source boundaries

- `frontend/src/app/`: routes, metadata, global design tokens/styles, loading/error/not-found boundaries.
- `frontend/src/components/`: shell, shared UI primitives, health context, preferences, incident/service views, charts, and page composition.
- `frontend/src/lib/`: sample types/data/filtering and the typed health client; unit tests are colocated.
- `backend/app/`: environment settings, SQLAlchemy setup, API and response schema.
- `backend/tests/`: health, CORS, schema, isolation, and failure tests.
- `scripts/`: real endpoint smoke verification.

Responsive CSS adapts the navigation and grid structure without changing data. Tables and preformatted evidence scroll inside their own containers. Native modal dialogs provide focus containment and Escape dismissal; focus-visible outlines, text/symbol status labels, and reduced-motion rules support accessibility. These are implementation measures, not a claim of a completed accessibility audit.

## Later phases: planned

```text
Dockerized Express microservices (Phase 2 implemented) → future telemetry ingestion
                                    ↓
                               FastAPI + SQLite
                                    ↓
                Codex SDK investigation and evidence orchestration
                  ↙                 ↓                 ↘
             Git history       RAG retrieval       test sandbox
                                    ↓
                   Sentence Transformers + Qdrant
```

Later work will establish incident persistence and workflow APIs, telemetry ingestion, historical indexing, evidence citations, Git inspection, patch proposals, and controlled test execution. These modules are documented reserved directories, not running integrations. Execution authorization, authentication, secrets handling, sandboxing, and audit trails must be designed before exposing agent actions.

## Validation strategy

Frontend tests cover combined filters and the health contract, including malformed/error/network responses. Backend tests cover API success, isolated SQLite connectivity, database failure, unexpected errors, CORS allowed/disallowed origins and preflight, OpenAPI, and 404 behavior. Production build and HTTP smoke checks verify server output. Real browser rendering and interaction QA remain a separate validation step when a browser tool is available.

## Phase 2: implemented

```text
Loopback host ports → Compose network
3001 → user-service ← order-service :3002 ← payment-service :3003
        GET users      user lookup          order lookup + fee invariant
             \              |                  /
              shared Express request/error boundary
                 ├── JSON stdout request completion logs
                 └── bounded incident publisher → JSON stdout event adapter
                                                   (future transport injection)
```

Each service is an independent Node process/image. Source lives in `services/{user,order,payment}-service/`, shared code in `services/shared/`, and automated tests in `services/test/`. One locked npm dependency tree is installed separately in each image. Records are in-memory, bounded per process, and isolated from Phase 1 SQLite. Orders optionally validate users over HTTP; payments optionally validate order amount. Compose enables both dependencies and health-gated startup.

All fault routes require NODE_ENV=development and ENABLE_FAULT_INJECTION=true. Defaults disable faults. Simulations are request scoped and recover without restarts. The Git regression uses a source fixture and performs no Git operation. One bounded memory allocation may run at a time. Docker limits resources and publishes loopback ports only.

The publisher emits schema-conforming events after error responses without blocking them. It has a deadline and concurrency bound, suppresses transport exceptions, and supports future injected transports. The default adapter writes nested incident_event objects to stdout. Delivery is best effort with no persistence or automatic retry. See [contract](INCIDENT_EVENT_CONTRACT.md) and [simulation guide](INCIDENT_SIMULATION.md).

FastAPI, SQLite, frontend components and dashboard data sources retain Phase 1 behavior. Phase 3 ingestion, incident persistence and automation have not begun.

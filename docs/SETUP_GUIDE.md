# Local setup — Phases 1–4

Use Node.js 22.18+ and Python 3.11+. Verified runtime: Node 24.13.1, Python 3.14.3 on macOS. From project root:

```sh
cd backend
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock.txt
cd ../frontend
npm ci
cd ../services
npm ci
```

For the fastest reproducible setup with safe disposable data and matching credentials, follow [PHASE3_DEMO.md](PHASE3_DEMO.md). For persistent local use, configure backend/.env (or export environment variables) and start FastAPI from backend/ so relative SQLite paths stay consistent.

## Backend configuration

| Variable | Default / behavior |
| --- | --- |
| DATABASE_URL | sqlite:///./opsguard.db; use an absolute SQLite path when changing working directories |
| ENVIRONMENT | development |
| CORS_ORIGINS | JSON array containing http://localhost:3000 and http://127.0.0.1:3000 |
| INCIDENT_WEBHOOK_TOKEN | Empty; ingestion returns 503 until configured |
| DEDUP_WINDOW_SECONDS | 300; range 1–86400 |
| MONITOR_ENABLED | true |
| MONITOR_INTERVAL_SECONDS | 10; range 0.1–3600 |
| MONITOR_TIMEOUT_SECONDS | 1; range 0.05–5 |
| MONITOR_DEGRADED_MS | 500; a slower successful check is Degraded |
| USER_SERVICE_URL | http://127.0.0.1:3001 |
| ORDER_SERVICE_URL | http://127.0.0.1:3002 |
| PAYMENT_SERVICE_URL | http://127.0.0.1:3003 |
| ENABLE_INCIDENT_MANAGEMENT | false |
| INCIDENT_MANAGEMENT_TOKEN | Empty; separate from webhook credentials |

Generate a strong server-only token, for example using `python3 -c 'import secrets; print(secrets.token_urlsafe(32))'`, and configure the identical value in backend and services. Do not log it or commit environment files. Read APIs have no user authentication and should remain local. Management additionally requires development environment and loopback client. Host monitoring URLs must be HTTP(S) without embedded credentials, query or fragment. URL settings are trusted operator configuration, not accepted from HTTP clients.

```sh
# From backend/, after configuration:
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Startup adds incident tables with SQLAlchemy create_all and preserves existing data. No schema migration framework is introduced. Use a single local Uvicorn worker to avoid redundant service-polling tasks. Stop with Control-C; monitor requests have bounded timeouts and the task is awaited on shutdown.

## Service configuration

Services read exported process environment, not backend/.env. Direct Node starts do not automatically load services/.env; source the demo file or export values yourself. Compose reads services/.env for substitution.

```sh
# From services/, after exporting INCIDENT_WEBHOOK_TOKEN:
INCIDENT_INGESTION_URL=http://127.0.0.1:8000/api/incidents/events npm run start:user
USER_SERVICE_URL=http://127.0.0.1:3001 INCIDENT_INGESTION_URL=http://127.0.0.1:8000/api/incidents/events npm run start:order
ORDER_SERVICE_URL=http://127.0.0.1:3002 INCIDENT_INGESTION_URL=http://127.0.0.1:8000/api/incidents/events npm run start:payment
```

Use separate terminals. Fault routes additionally require NODE_ENV=development and ENABLE_FAULT_INJECTION=true. They stay disabled otherwise. Never expose the fault stack publicly. See [simulation guide](INCIDENT_SIMULATION.md).

Docker remains optional and unverified at runtime here. From services/, set a reachable ingestion URL in the environment, then run `docker compose config`, `docker compose up --build -d --wait`, `docker compose ps`, `docker compose logs --follow`, and `docker compose down`. On Docker Desktop for macOS, the host API URL can use host.docker.internal; inside another Docker network use its configured backend DNS name. localhost inside a container is the container itself. The host API bind and firewall must permit the selected container route; exposing a host API beyond loopback is a separate local operator decision, not done automatically. Static Compose checks do not prove connectivity or container health.

## Frontend

```sh
cd frontend
npm run dev
```

NEXT_PUBLIC_API_URL defaults to http://127.0.0.1:8000. Change it in frontend/.env.local before building/starting if needed. This is public configuration; never include webhook or management credentials. Exact frontend origin must be permitted in CORS_ORIGINS. Configured trusted origins support GET, PATCH and knowledge-search POST preflights. Webhook POST still requires its server-only token.

The dashboard polls summary/services centrally and incident pages/details locally every five seconds after completion. Requests abort on unmount or filter change; offline retry is ten seconds, with stale-data warnings. Search is debounced 300ms. No background queue or WebSocket is used. Time displays use UTC. Empty databases show no sample records. AI investigation remains planned; historical retrieval is now available through Phase 4.

## Checks and troubleshooting

Frontend: `npm test`, `npm run typecheck`, `npm run lint`, `npm run format:check`, `npm run build`. In this environment default Turbopack hits a process/port permission error even after retry; separately verify `npm run build -- --webpack`. The default script is unchanged.

Backend: `.venv/bin/python -m pytest -q`, `.venv/bin/python -m pip check`. Services: `npm test`, including JSON Schema validation. Full real-process pipeline: `backend/.venv/bin/python scripts/check-incident-pipeline.py` from root. Original smoke checks remain available: `python3 scripts/check-health.py` and `python3 scripts/check-pages.py` with their servers running.

- 401 webhook: check matching exported tokens. A backend .env does not configure Node automatically.
- 503 webhook: backend token is absent. A service with no ingestion URL only writes local events.
- PublicationFailure: inspect safe service logs; check URL, token, backend availability and host routing. Delivery retries are bounded; prolonged outages can lose events.
- No dashboard data: verify /api/incidents and NEXT_PUBLIC_API_URL; wait for the five-second poll. The frontend never falls back to demo data.
- Unavailable services: check their actual ports, URLs and health endpoints. Three failed checks classify Unavailable; successful recovery resets failures. Uptime is not calculated.
- SQLite path confusion: start from backend/ or configure an absolute path. Keep the same path on restart.
- Empty demo: source the SAME generated environment file in both terminals. Use the cleanup helper only on stopped, marked disposable demos.
- Default Turbopack build failure: record the error and use the separately verified webpack command; do not claim the default build passed.


## Phase 4 optional RAG stack

The verified Python 3.14 backend environment supports the ML stack; no destructive environment replacement or system-wide package install was needed. From backend/, install `requirements-rag.lock.txt` for the full pinned optional stack, then follow [RAG_PIPELINE.md](RAG_PIPELINE.md) to index sources before starting FastAPI. Existing requirements.lock.txt remains the preserved core stack. A complete pinned model is cached on this machine; new machines require approval for about 92 MB of model assets. Runtime uses local_files_only and never silently substitutes embeddings.

Default Qdrant is persistent embedded storage at knowledge/.qdrant. Use exactly one API worker, and stop the API before an indexing/evaluation CLI uses the same path. A path lock is expected if two processes compete; it does not mean data was deleted. QDRANT_URL switches to a separately running server; QDRANT_API_KEY stays server-only. Do not describe local mode as a Qdrant HTTP server. Docker is unavailable and server/container verification remains pending.

Open /knowledge for real collection counts, model configuration, source browsing and search. Current incident dialogs provide Find Similar Historical Incidents. No operation resolves incidents or invents an AI diagnosis. All curated historical records are labeled synthetic.

For integration: from root run `backend/.venv/bin/python scripts/check-knowledge-pipeline.py`. For real-model pytest: from backend/ run `HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 OPSGUARD_RAG_INTEGRATION=1 .venv/bin/python -m pytest -q`. Routine tests skip the external-model integration unless explicitly enabled; no model downloads occur. [RAG_EVALUATION.md](RAG_EVALUATION.md) records measured results and limitations. Missing model/Qdrant returns a clear retrieval error while health/incident APIs continue working.


## Phase 5 read-only investigations

From agent/: `npm ci`, then `npm test`. No new Python runtime dependencies are required. Keep using the existing backend environment and its incident/RAG setup. In VS Code select backend/.venv/bin/python, and use separate terminals for backend, frontend and services.

AGENT_EXECUTION_ENABLED defaults false. Private backend settings are AGENT_AUTH_TOKEN (dedicated local action token), AGENT_CODEX_API_KEY (dedicated server-only provider credential), AGENT_CODEX_MODEL (explicit actual account model), AGENT_PROJECT_ROOT (default project, service-only source allowlist), AGENT_TIMEOUT_SECONDS (90, bounded 5–180) and AGENT_QUEUE_LIMIT (8, bounded 1–20). No credentials belong in NEXT_PUBLIC variables or browser storage. Use one backend worker.

**Current blocker:** the required native macOS containment probe terminates with SIGABRT, so live Codex execution is unavailable even with credentials. No paid request was made. Do not bypass isolation, use full-access execution or treat a disposable workspace alone as protection. See [workflow](INVESTIGATION_WORKFLOW.md) for the exact separate non-AI probe, guarded live test and explicitly labeled test-double demo. Other platforms need a separately verified containment implementation.

The /investigations page and incident action show actual readiness and persistent job state. Starts/cancels require loopback development authentication; starts additionally require paid-use confirmation. Empty/offline/failed/cancelled states never show fake AI findings. Backend restart marks unfinished work failed or cancels active work on clean shutdown. No automatic paid retry/resume occurs.

The original project has an inherited home-directory Git root, which is deliberately rejected. A new disposable synthetic Git fixture can be created with `backend/.venv/bin/python scripts/prepare-investigation-fixture.py`; actual project Git history is untouched. Read [AGENT_ARCHITECTURE.md](AGENT_ARCHITECTURE.md) and [AGENT_EVALUATION.md](AGENT_EVALUATION.md) before enabling live operation or benchmarking. Phase 6 and hotfix generation are not implemented.

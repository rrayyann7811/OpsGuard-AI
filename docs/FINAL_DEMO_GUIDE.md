# OpsGuard AI final local demonstration

Phase 5.14 preserves the existing architecture and owner data. Browser automation remains unavailable; use the detailed manual browser acceptance checklist (local-only reference; not included in this release). The owner previously verified website/API connectivity, service outage/recovery, local semantic retrieval and preferences. Fresh model-free verification is in Phase 5.14 (local-only reference; not included in this release); full semantic retrieval results from Phase 5.13 (local-only reference; not included in this release) remain historical. Real Ollama inference remains **pending**. Deterministic reports are labeled TEST DOUBLE and do not establish AI accuracy.

## Starting the application

Use separate terminals. These commands use installed dependencies. Check for existing listeners before starting duplicates; do not terminate an owner's process to free a port. Keep one FastAPI process for embedded Qdrant and the sequential investigation worker. Do not run a build alongside the frontend development server.

Backend (existing local SQLite data; AI disabled):

```sh
cd '/path/to/OpsGuard-AI/backend'
AGENT_EXECUTION_BACKEND=local-ollama AGENT_OLLAMA_MODEL=llama3.2:3b \
AGENT_EXECUTION_ENABLED=false AGENT_MANAGED_ENABLED=false AGENT_MANAGED_HTTP_ENABLED=false \
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Frontend:

```sh
cd '/path/to/OpsGuard-AI/frontend'
NEXT_PUBLIC_API_URL=http://127.0.0.1:8000 npm run dev -- --webpack
```

User service:

```sh
cd '/path/to/OpsGuard-AI/services'
NODE_ENV=development ENABLE_FAULT_INJECTION=false HOST=127.0.0.1 PORT=3001 npm run start:user
```

Order service:

```sh
cd '/path/to/OpsGuard-AI/services'
NODE_ENV=development ENABLE_FAULT_INJECTION=false HOST=127.0.0.1 PORT=3002 npm run start:order
```

Payment service (faults disabled for ordinary use):

```sh
cd '/path/to/OpsGuard-AI/services'
NODE_ENV=development ENABLE_FAULT_INJECTION=false HOST=127.0.0.1 PORT=3003 npm run start:payment
```

Website: **http://127.0.0.1:3000**. API: http://127.0.0.1:8000/docs. A frontend already built with a different public API origin requires rebuilding to change that origin.

## Demonstrating monitoring

1. Open Services and wait for three Healthy badges. A slow responding service can be Degraded.
2. Press Control-C only in your payment terminal. The default backend check interval is 10 seconds. The first two failed checks are Degraded; the third is Unavailable. Dashboard polls every five seconds, so allow an additional polling interval.
3. Inspect consecutive failures, last attempt and preserved last successful check.
4. Restart the same payment command. A successful health contract resets failures to zero and updates last success. Response time still determines Healthy versus Degraded.
5. Health-check failures are in-memory observations. They do **not** automatically create SQLite incidents. Service incident counts show persisted application events, not failed probes.

## Demonstrating incident detection in isolated data

Use an isolated environment instead of the owner's existing database. If normal backend/payment terminals are running on ports 8000/3003, stop only those you started with Control-C before replacing them. Otherwise coordinate with the owner; do not kill arbitrary listeners. User/order and frontend can remain running.

```sh
cd '/path/to/OpsGuard-AI'
python3 scripts/prepare-incident-demo.py
```

Use the **exact** `source .../environment.sh` command printed by this run in BOTH backend and payment terminals. Never source an illustrative `/private/tmp/...` path. Never display the environment file or its webhook token. Preparation creates a private, new `backend/.demo/phase3-…` directory, separate SQLite/Qdrant paths, matching webhook credentials, development-only faults and disabled AI/management execution.

Backend terminal, after sourcing the printed path:

```sh
cd '/path/to/OpsGuard-AI/backend'
AGENT_EXECUTION_ENABLED=false AGENT_MANAGED_ENABLED=false AGENT_MANAGED_HTTP_ENABLED=false \
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Payment terminal, after sourcing the SAME path:

```sh
cd '/path/to/OpsGuard-AI/services'
HOST=127.0.0.1 PORT=3003 npm run start:payment
```

Trigger the documented controlled failure:

```sh
curl -i --request POST http://127.0.0.1:3003/simulate/payment-failure \
  --header 'Content-Type: application/json' --data '{}'
```

Expected: **HTTP 502**, `PaymentFailure`, `Simulated payment processor rejection`, and a request ID. This is a labeled controlled simulation, persisted through the real authenticated webhook. Allow publication and five-second website polling.

- Open Incidents: one OPEN/high payment incident; inspect ID, service, first/latest times and count 1.
- Open its details: error type, HTTP status, sanitized stack and request/event evidence; investigation state and available historical-context action.
- Open Overview and Analytics: one active incident, severity high = 1, one stored event; service summary agrees.
- Repeat the same curl within 300 seconds: one incident, count 2, distinct request/event IDs, event chart count 2. Same-event redelivery is idempotent; a new matching fault is a new occurrence.
- Restart only the isolated FastAPI process with the same sourced environment: data remains.
- The isolated Qdrant directory starts empty; it deliberately does not reuse or reindex the owner's knowledge collection. Return to the ordinary backend environment for the existing 24-record library.

Evidence and databases remain for review. Do not run the cleanup utility without explicit owner authorization. To return to normal data, stop your demo backend/payment terminals, open fresh terminals without the sourced demo variables and use the ordinary startup commands.

## Automated isolated integration

From project root, run sequentially while memory pressure is normal:

```sh
backend/.venv/bin/python scripts/check-incident-pipeline.py
backend/.venv/bin/python scripts/check-investigation-workflow.py --without-embeddings
```

Each prints its new evidence directory and stops only its own child processes. Disposable data is preserved by default. The model-free investigation option skips indexing, blocks embedding initialization and explicitly reports missing historical context; it does not verify semantic retrieval. The first checks real three-service health/outage/recovery, authenticated incident ingestion, SQLite restart persistence, React polling/details/metrics/charts and occurrence deduplication. These are real HTTP/DOM checks, not rendered browser QA. The full `check-knowledge-pipeline.py` and default `check-investigation-workflow.py` runners load cached MiniLM. Do not run those modes while model loading is prohibited; they require a separate exception. Do not pass `--local-ollama`.

## Demonstrating historical knowledge

Use the ordinary backend with its existing local Qdrant path, not the empty incident-demo index. Open Historical Knowledge: 24 synthetic sources, attribution, service/severity filters, causes and resolutions. A query exercised by the real integration is:

> Payment fee was subtracted instead of added to the total

The final owner queries to verify later, after permission to load cached embeddings, are:

1. `Why is the payment service calculating the wrong transaction total?` — expected relevant result: `Fee subtraction introduced payment total regression` (`SYN-PAY-004`).
2. `Database connection failed while processing payments` — select `payment-service` and `critical`; expected relevant result: `Payment ledger database connection failure` (`SYN-PAY-003`). Every returned result must match both filters.

These exact queries have not received fresh semantic verification in Phase 5.14. Their expected source records exist in the unchanged dataset. Do not treat the model-free request/filter test as proof of relevance.

Inspect the historical result, its runbook and source reference. Similarity is cosine similarity, not diagnosis confidence. Loading cached MiniLM on first search consumes memory; no Ollama model is needed. Do not reindex an existing healthy collection.

## Demonstrating investigations

The automated deterministic runner creates its own incident, restricted source/Git fixture and validated report. In `--without-embeddings` mode it supplies no historical matches and the report must state that limitation. Inspect its passing log and retained SQLite evidence. Its adapter is explicitly TEST DOUBLE. Ordinary Settings shows the selected execution backend/model, daemon and installed-model inventory when checkable, memory admission, disabled execution and pending real inference. It does not start Ollama. Normal website investigation history shows queued/active stages, completed, failed and cancelled states; recommendations remain advisory.

For a later real test, follow the **separate later manual AI checklist** in [WEBSITE_OWNER_TESTING.md](WEBSITE_OWNER_TESTING.md#4-separate-later-manual-ai-checklist) and [local AI documentation](LOCAL_AI_INVESTIGATION.md). Obtain owner authorization, use only installed `llama3.2:3b`, pass the unchanged memory guard again after retrieval, and request one explicit investigation. Do not start the daemon, enable execution, load/download a model, lower thresholds or infer verified diagnosis from a deterministic report during this demonstration.

## Manual website checklist

- [ ] Navigate Overview, Incidents, Services, Investigations, Historical Knowledge, Analytics and Settings.
- [ ] Review 390, 768, 1024 and 1440 px; check table scrolling, dialogs, navigation, focus and keyboard dismissal.
- [ ] Search/filter/page incidents; inspect genuine stored event evidence.
- [ ] Observe automatic metrics/chart updates after each isolated fault.
- [ ] Observe health failure/recovery without additional persisted incidents.
- [ ] Verify knowledge filters, source details and similarity labels.
- [ ] Verify investigation failures and pending inference are displayed honestly.
- [ ] Check backend disconnect/reconnect states and preference persistence.

Browser interactions and four-width rendered layouts remain owner verification gates when no browser automation tool is available.

## Stopping safely

Press **Control-C in each terminal you started**: frontend, FastAPI, user, order and payment. Integration runners stop their own children by process handle. Do not use `pkill`, broad process-group kills, Docker shutdown, database deletion or model removal. Preserve all demo directories, original SQLite/Qdrant storage and model caches. No Ollama daemon is started by these instructions.

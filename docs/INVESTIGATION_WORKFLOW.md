# Selected workflow — Local AI Investigation

Option B uses `local-ollama`. **Implemented — live local inference pending.** Start the existing backend/frontend/services as usual; AI remains disabled until explicitly configured and locally authorized. Phase 5.11 verified Ollama startup and the installed 3B/8B inventory, but the unchanged memory gate blocked generation. The owned daemon was stopped; no model loaded or downloaded. Managed execution remains disabled and the blocked Codex sandbox is unchanged.

**Phase 5.11 result:** `OLLAMA_MEMORY_INSUFFICIENT` — approximately 3.32 GiB required headroom versus 2.02–2.04 GiB sampled reclaimable memory. No real investigation/report was created. Verification details (local-only reference; not included in this release). Do not lower the guard or relabel deterministic results as local AI verification. Free sufficient memory through owner-controlled actions before another controlled attempt; do not stop unrelated processes automatically. Phase 5.12 remains unstarted.

For the selected path, use [LOCAL_AI_INVESTIGATION.md](LOCAL_AI_INVESTIGATION.md): runtime/model preflight, backend-only settings, `authorize_local_execution: true`, existing progress/report APIs, conservative memory controls, cancellation/restart reconciliation and the opt-in real end-to-end demonstration. Existing application-controlled collectors perform all source/Git inspection; the model receives only bounded evidence and has no tools. A valid uncertain result is insufficient evidence; invalid/fabricated output fails without fallback. Running with AI disabled preserves the rest of the application.

The existing deterministic Phase 5 runner remains unchanged in default behavior. Its new `--local-ollama` mode requires a separate explicit authorization marker and never starts Ollama. It is not run during routine tests. The ten-case real-model evaluation is prepared with null metrics and remains pending.

The following Codex instructions are retained as historical documentation of preserved functionality, not the selected workflow or authorization for paid execution.

# Investigation workflow and macOS demonstration

Phase 5 status: **Implemented — live Codex verification pending.** The current containment health probe fails with SIGABRT. Keep live execution disabled until that blocker is resolved and the non-AI probe passes. No paid resources were used during implementation.

## Install and open in VS Code

Open the existing OpsGuard AI folder. Use backend/.venv/bin/python as the Python interpreter. Keep existing backend/frontend/service setup; install the dedicated adapter separately:

```sh
cd agent
npm ci
npm test
```

No global SDK/Docker installation is required. Existing `backend/requirements-rag.lock.txt` supplies the optional RAG stack; the cached pinned model remains offline. Keep the same DATABASE_URL for persistent investigation history.

## Configuration and authorization

Backend environment variables (private backend/.env or exported variables):

| Variable | Default / purpose |
| --- | --- |
| AGENT_EXECUTION_ENABLED | false; explicit live-run opt-in |
| AGENT_AUTH_TOKEN | Empty; separate local action token |
| AGENT_CODEX_API_KEY | Empty; dedicated server-only API key, never inherited from the user's Codex session |
| AGENT_CODEX_MODEL | Empty; choose an actually available Codex model explicitly |
| AGENT_PROJECT_ROOT | Absolute project-derived path; source remains restricted to approved service directories |
| AGENT_TIMEOUT_SECONDS | 90; range 5–180 |
| AGENT_QUEUE_LIMIT | 8; range 1–20 |

Never put these secrets in NEXT_PUBLIC configuration, source, logs or Git. Do not reuse webhook credentials as an agent trigger token. Trigger/cancel requires a loopback client, ENVIRONMENT=development and a matching `Authorization: Bearer <AGENT_AUTH_TOKEN>` header. Starting also requires JSON boolean `authorize_paid_execution: true`. The UI requires a separate paid-usage checkbox and clears its one-use token field after submission; nothing is saved to browser storage.

Backend starts normally from backend/:

```sh
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Use a single backend worker. Frontend: from frontend/, `npm run dev`, or `npm run dev -- --webpack` for this environment's Turbopack permission issue. Open /investigations. Empty/unavailable states are honest; no sample AI report is generated.

## Non-AI containment check

```sh
cd agent
# Run only after a meaningful runtime/policy change, not as an unchanged retry loop.
OPSGUARD_SANDBOX_TEST=1 npm test
```

This does not call OpenAI. On this host the opt-in OS probe failed because sandboxed processes exited with SIGABRT, even the allowed sentinel read. Routine agent unit tests pass with that probe explicitly skipped. The adapter's configuration endpoint remains unavailable when the required probe fails; do not bypass it or change to full-access execution. macOS ARM64 is the initial target; other platforms require an equivalent verified isolation launcher. Actual live provider authentication/model availability also remains unverified. The final changed diagnostic still failed before the SDK; signature checks passed in the approved diagnostic context, so do not infer SDK corruption from earlier restricted-context verification errors. Failed runtime readiness is cached until backend restart; after an approved fix, restart FastAPI before rechecking.

## APIs

| Method | Endpoint | Behavior |
| --- | --- | --- |
| GET | /api/investigations/configuration | Safe readiness, read-only/auth/paid-authorization information |
| POST | /api/incidents/{incident_id}/investigate | Authorized creation; 202 and QUEUED record |
| GET | /api/investigations | Paginated newest-first list; optional incident_id filter |
| GET | /api/investigations/summary | Actual total/completed/running/failed/cancelled and completed-duration mean |
| GET | /api/investigations/{id} | State, metadata, evidence and report if accepted |
| GET | /api/investigations/{id}/events | Paginated persisted timeline/tool audit |
| GET | /api/investigations/{id}/report | Completed validated report; otherwise 409 |
| POST | /api/investigations/{id}/cancel | Authenticated terminal cancellation |

Missing records return 404; malformed inputs 422; missing/bad credentials 401 (unconfigured token 503); non-local/non-development actions 403; duplicate active job/invalid terminal action 409; full queue 429; unavailable worker/SDK/containment 503. Listing/events page sizes are bounded to 100. Read APIs retain the project's local-development exposure boundary, not production user authorization.

After resolving containment and obtaining explicit paid-use authorization, a local caller can start a real run:

```text
POST http://127.0.0.1:8000/api/incidents/<actual-incident-uuid>/investigate
Authorization: Bearer <dedicated-local-agent-token>
Content-Type: application/json

{"authorize_paid_execution":true}
```

The frontend offers the same action from a persisted incident, displays progress, and links to /investigations#<id>. No automatic invocation occurs on incident ingestion. Interrupted requests are not automatically retried because a job may already have been accepted; inspect the list first. The unique active-job constraint prevents concurrent duplicate investigations, while a new explicitly authorized run is allowed after termination.

## Real intended demonstration

1. Follow the existing Phase 3 demo to start FastAPI, frontend and payment service with matching webhook credentials.
2. Prepare historical knowledge before API startup, or use a separately configured Qdrant server. Do not contend for an embedded path from a second process.
3. Trigger a controlled payment failure and verify its persisted incident.
4. Open incident details and inspect historical matches.
5. If actual containment/readiness passes and paid use is explicitly authorized, choose Investigate with AI and enter the local agent token/confirmation.
6. Observe persistent source/RAG/Git collection events, then the structured report if Codex succeeds.
7. Verify report citations and limitations. A suspected cause is a hypothesis; status remains unchanged.

**Steps requiring live Codex were not executed here and must not be presented as passed.** For the original project, useful Git history is unavailable because its inherited Git root is outside the project. The agent reports this instead of inventing commits.

For a controlled Git example, create a new disposable fixture:

```sh
# From root; writes only a newly generated temporary directory:
backend/.venv/bin/python scripts/prepare-investigation-fixture.py
```

It prints its own fixture path and actual faulty commit SHA. This fixture copies approved microservice sources, commits a correct fee addition and then a known faulty subtraction. Set AGENT_PROJECT_ROOT to the printed path only for a controlled demonstration. These are explicitly synthetic fixture commits, not project history; no original Git history is rewritten. The fixture builder is test/development tooling, not an agent capability.

## Verified surrounding workflow, explicitly a test double

```sh
# Project root; no API key required and no Codex request:
backend/.venv/bin/python scripts/check-investigation-workflow.py
```

This starts real FastAPI and payment processes, triggers an actual controlled failure, uses real local model/Qdrant retrieval, reads authorized source, inspects actual scoped Git fixture commits, persists lifecycle/evidence/report, and checks the actual React UI over HTTP. Only the reasoning adapter is an explicitly injected deterministic TEST DOUBLE. All report/UI metadata says so. Original service hashes and incident OPEN status are checked. This verifies application wiring, **not live AI reasoning or root-cause accuracy**. Temporary SQLite/index/Git paths are owned by the runner and cleaned up; the normal index/database are untouched.

## Tests

```sh
cd backend
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 OPSGUARD_RAG_INTEGRATION=1 .venv/bin/python -m pytest -q
.venv/bin/python -m pip check
cd ../frontend
npm test
npm run typecheck
npm run lint
npm run format:check
npm run build
npm run build -- --webpack
```

The real Codex test is separate and intentionally skipped by default. Only after containment is verified, credentials/model are configured and paid use is explicitly authorized:

```sh
# Do not run until those preconditions hold; may incur charges:
cd backend
OPSGUARD_LIVE_CODEX_TEST=I_AUTHORIZE_PAID_EXECUTION .venv/bin/python -m pytest -q tests/test_investigations.py -k opt_in_live
```

It uses the actual CodexAdapter and fails if unavailable; it never falls back to a test double. Stop/restart behavior is persistent: graceful active cancellation or crash recovery FAILED/BACKEND_RESTART, never fabricated completion.


## Final audit results

- Passed: backend 74 tests (including genuine cached-model/local-Qdrant test), microservices 25, frontend 26, TypeScript, ESLint, formatting, dependency checks and webpack production build.
- Skipped in routine suites: one paid live Codex test; three process-backed frontend tests; one host-containment adapter probe. The three process-backed frontend tests passed separately through their integration runners.
- Passed separately: Phase 3 real incident pipeline; Phase 4 real historical retrieval; Phase 5 real service/RAG/source/fixture-Git/SQLite/React workflow with an explicit TEST DOUBLE, not real Codex reasoning.
- Failed/blocked: changed non-AI sandbox diagnostic terminated with SIGABRT; live Codex and actual AI benchmarking were not run. No paid resource usage.
- Additional verification: all 24 saved RAG query rankings and quality metrics remained unchanged for semantic/metadata/hybrid comparisons. The original evaluation artifact was not overwritten.

The final audit did not rerun the known failing default Turbopack build; webpack was explicitly built and passed. Docker runtime/server mode and visual browser QA remain unverified. See PROJECT_PROGRESS.md and evaluation/phase5_audit.json for the exact current checkpoint. Phase 6 is not started.

# Website owner testing — Phase 5.12

The website supports local incident monitoring, historical evidence, investigation history and read-only AI readiness. Real local inference is **not verified**. Phase 5.12 performs no model startup, model loading or generation. Application configuration is server-side; the Settings page does not write environment files or show credential values.

## 1. Start the website without AI

From the existing project, use the installed environments/dependencies. Do not overwrite an existing `.env` or database. The optional `.env.example` now includes the intended `llama3.2:3b` selection, but execution remains disabled and the application default still requires explicit model selection.

Terminal 1:

```sh
cd '/path/to/OpsGuard-AI/backend'
AGENT_EXECUTION_BACKEND=local-ollama AGENT_OLLAMA_MODEL=llama3.2:3b \
AGENT_EXECUTION_ENABLED=false \
AGENT_MANAGED_ENABLED=false AGENT_MANAGED_HTTP_ENABLED=false \
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Terminal 2:

```sh
cd '/path/to/OpsGuard-AI/frontend'
npm run dev -- --webpack
```

Open **http://127.0.0.1:3000**. Backend documentation: http://127.0.0.1:8000/docs. The frontend defaults to that backend origin; use `NEXT_PUBLIC_API_URL=http://127.0.0.1:8000` in a private frontend `.env.local` only when needed, and restart Next.js after changing it. No AI key belongs in NEXT_PUBLIC variables.

A production-mode alternative, when memory permits, is `NEXT_TELEMETRY_DISABLED=1 npm run build -- --webpack` followed by `npm start` in the frontend directory. Do not run build and dev simultaneously. Memory pressure may require deferring a build; this is distinct from an application test failure.

No Docker or Ollama runtime is needed to browse the website. Unstarted microservices show Unknown/Unavailable rather than invented uptime. Missing/unavailable Qdrant context shows an explicit retrieval error; it does not silently create historical results. Existing SQLite/Qdrant paths are preserved; use only one backend process for embedded Qdrant and sequential investigations.

## 2. Create a controlled incident without touching existing data

For an isolated demonstration, the existing helper creates a **new** disposable SQLite environment and matching local webhook credentials:

```sh
cd '/path/to/OpsGuard-AI'
python3 scripts/prepare-incident-demo.py
```

Copy the exact `source .../environment.sh` command printed by that helper into BOTH the backend and payment-service terminals before starting them. It selects the new demonstration database; stop the current backend first and restart it with the same sourced environment. Do not print or share the private environment file. To use the current database instead, preserve its `DATABASE_URL` and configure matching `INCIDENT_WEBHOOK_TOKEN` values privately in both processes.

Payment terminal, after sourcing the generated environment:

```sh
cd '/path/to/OpsGuard-AI/services'
HOST=127.0.0.1 npm run start:payment
```

The helper supplies `NODE_ENV=development`, `ENABLE_FAULT_INJECTION=true`, webhook origin/token and the disposable database path. Payment defaults to port 3003. Optional user/order services use `npm run start:user` and `npm run start:order` from `services/`; do not start them merely to make every health badge green.

Trigger the existing payment regression with a loopback request:

```sh
curl --request POST http://127.0.0.1:3003/simulate/faulty-commit \
  --header 'Content-Type: application/json' --data '{}'
```

HTTP 500 is expected: the existing deliberately faulty fixture subtracts the fee, producing 9,800 instead of 10,200 cents. No source edit is needed. Confirm the persisted incident in `/incidents`, its timestamps/event evidence and the actual service status. These are controlled demonstration records, not production telemetry. The current missing-amount scenario returns a guarded HTTP 400; do not remove validation to force a 500.

## 3. Website checklist — no LLM required

- [ ] Overview shows actual incident/service counts, severity and all-time investigation activity; no fabricated production statistics.
- [ ] Incidents support search, severity/status/service filters, pagination and details with error/stack/event evidence.
- [ ] Service cards show actual health/attempts and stored incident counts; “View service incidents” selects the service filter.
- [ ] Investigations show honest empty/running/failed/completed states, model/backend provenance and actual measured durations where recorded.
- [ ] Completed reports identify schema/provenance acceptance separately from causal correctness. Citation links open the referenced collected evidence. Remediation remains advice, never an executable hotfix.
- [ ] Historical Knowledge labels the synthetic dataset, displays source/resolution references, and reports missing retrieval honestly. A RAG search uses the configured local embedding model; do this later only when model loading/resources are acceptable.
- [ ] Analytics labels its event-day selection and all-time counts. It does not claim request-rate or uptime measurements.
- [ ] Settings preserves browser preferences, tests the backend connection and displays separate AI readiness stages.
- [ ] Inspect widths approximately 390, 768, 1024 and 1440 pixels; check navigation, table scrolling, dialogs, filters, keyboard focus, readable labels and errors.
- [ ] Disconnect/reconnect the backend and verify error/retry/stale-state messaging. Do not interpret an unavailable service or empty database as a healthy result.

## 4. Separate later manual AI checklist

**Do not perform this section during Phase 5.12.** It may load the existing model and generate real output. The owner must choose when to proceed after website testing and resource readiness.

1. Keep managed execution disabled. Select `AGENT_EXECUTION_BACKEND=local-ollama`, `AGENT_OLLAMA_MODEL=llama3.2:3b` and `AGENT_OLLAMA_URL=http://127.0.0.1:11434` in the private backend environment. Initially leave `AGENT_EXECUTION_ENABLED=false`.
2. Set a separate private `AGENT_AUTH_TOKEN` for local start/cancel actions. Never put it in frontend configuration or logs; enter it only into the local action form when needed.
3. Inspect memory pressure and swap using the read-only commands below. Do not stop unrelated processes automatically. The historical cold-load requirement was about **3.32 GiB** for this installed model; a reclaimable estimate is not a reservation, and RAG needs additional memory.

```sh
/usr/bin/memory_pressure -Q
/usr/bin/vm_stat
/usr/sbin/sysctl kern.memorystatus_vm_pressure_level vm.swapusage
```

4. Start the existing Ollama service manually in its own terminal, only when you are ready. No system configuration or model download is required:

```sh
OLLAMA_HOST=127.0.0.1:11434 OLLAMA_NO_CLOUD=1 \
OLLAMA_MAX_LOADED_MODELS=1 OLLAMA_NUM_PARALLEL=1 OLLAMA_KEEP_ALIVE=0 \
ollama serve
```

If an existing instance is already running, inspect it rather than starting another. Keep it loopback-only and local-only. In another terminal, `ollama --version`, `ollama list` and `ollama ps` are read-only checks. Confirm the exact existing `llama3.2:3b` name. **Do not pull, replace or delete models.** The prior CLI MLX warning did not prevent inventory access, but genuine generation remains untested.

5. Open Settings → **Check AI readiness**, or inspect the same safe endpoint:

```sh
curl http://127.0.0.1:8000/api/investigations/readiness
```

This uses read-only inventory/loaded-model queries and the existing memory guard; it never generates text or starts Ollama. Distinguish configured model, reachable server, installed model and memory passed/blocked/not checked. Live inference stays “pending” even if these checks pass. A failure at any stage is not permission to lower the guard or substitute a test double.

6. Only after website testing and sufficient resources, explicitly set `AGENT_EXECUTION_ENABLED=true` in the backend environment and restart FastAPI with the same database/Qdrant configuration. Replace the earlier inline `AGENT_EXECUTION_ENABLED=false` launch override with `true` for this later authorized run; editing a dotenv file alone does not override an inline shell value. Verify readiness again. Open ONE controlled incident, enter the local action token, check authorization and start ONE investigation. Do not resubmit after an uncertain request or failed model response; inspect the stored job first. The application repeats memory admission after evidence collection.
7. Inspect progress, actual model/backend, submitted evidence, structured report, affected file ranges, Git attribution (only when collected), historical references, conceptual remediation and limitations. “Accepted” means schema/provenance validation passed, not that the diagnosis is correct. Compare the suspected cause independently against the controlled ground truth. A valid uncertain result is insufficient evidence; malformed/fabricated output is a failure.
8. Record prompt/output bytes, model/total duration and available memory metadata without inventing missing measurements. Do not infer general accuracy from one case. No model command or suggested fix is executed.
9. Cancel if needed through the authenticated local action. HTTP cancellation is best effort. If stop state is unconfirmed, independently stop/unload only your test generation and follow the existing authenticated idle-runtime reconciliation procedure in [LOCAL_AI_INVESTIGATION.md](LOCAL_AI_INVESTIGATION.md). Do not restart inference automatically.

## 5. Stop safely

Use Control-C in the terminals you started for backend, frontend and microservices. Stop the Ollama daemon with Control-C only if you started it specifically for this test and nobody else is using it. If only your test model remains loaded, `ollama stop llama3.2:3b` is the supported unload command; do not affect unrelated sessions. Keep SQLite databases, Qdrant storage, model files and generated demo environments for later inspection; no destructive cleanup command is required.

Existing real-model test/demo commands remain separately opt-in in [LOCAL_AI_INVESTIGATION.md](LOCAL_AI_INVESTIGATION.md). Do not combine them with a UI run: that would make more than one inference. Phase 6 autonomous remediation remains out of scope.

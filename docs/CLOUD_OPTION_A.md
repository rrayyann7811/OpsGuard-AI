# Option A — Vercel frontend and stateless Render API

**Prepared and tested locally; nothing deployed.** No hosted backend/frontend URL has been assigned or verified. Do not apply the Render blueprint or import/deploy on Vercel until separately authorized. No paid storage, database, microservice or model is included.

## Scope and backend audit

The local `app.main:app` creates SQLite tables, starts the investigation manager and, by default, polls local Express services. Knowledge endpoints lazily initialize Qdrant and embeddings; local investigation readiness can query Ollama. Those defaults remain unchanged for the local application and must not be used for Option A.

Render instead runs `app.hosted:app`. It does not import the local database, worker, monitor, Qdrant, embeddings or Ollama modules. It performs no outbound requests and creates no database/index. Even accidentally enabled local execution/monitoring environment flags cannot activate those components in this entry point. This profile intentionally cannot be converted into a write-enabled backend by setting a token.

| Endpoint | Option A behavior |
| --- | --- |
| GET /api/health | Real reachable-process health; production, hosted-readonly, database not_configured, storage stateless; disabled capability flags |
| GET /api/incidents and /summary | Empty lists/zero summaries; pagination/filter validation, no fabricated incident records |
| GET incident/detail/events | 404: no stored record |
| GET /api/services | Three Unknown/unobserved services; no health probes, no latency or successful timestamps invented |
| GET /api/investigations, /summary | Empty history/outcomes; no worker |
| GET investigation configuration/readiness | Disabled public capability summary; no token values, model inventory or memory probe |
| GET /api/knowledge/status | Unavailable/not deployed |
| GET historical sources/details | 503: Qdrant and embeddings are not deployed |
| POST/PATCH/PUT/DELETE, including ingestion/investigate/reconciliation/search | 403 before handlers; no privileged execution or writes |

These empty summaries mean **no storage configured**, not “no real incidents occurred.” The hosted frontend displays that distinction. Public OpenAPI documents only this restricted API. Historical retrieval, persisted incident processing and model investigation remain local-only.

## Render settings — owner deployment later

Repository: https://github.com/rrayyann7811/OpsGuard-AI, branch `main`.

| Setting | Exact value |
| --- | --- |
| Service type | Web Service, Python runtime |
| Suggested name | opsguard-ai-api (availability unverified) |
| Root directory | backend |
| Build command | pip install -r requirements.lock.txt |
| Start command | sh render-start.sh |
| Expanded start | python -m uvicorn app.hosted:app --host 0.0.0.0 --port "$PORT" --workers 1 |
| Health-check path | /api/health |
| Instance | Free, if available/eligible; stop if unavailable rather than choosing paid |
| Python | PYTHON_VERSION=3.14.10 |
| Auto deploy | Off for this preparation |
| Persistent disk / database | None |

`render.yaml` records these settings, with free plan and automatic deployment off. **Do not apply it now.** PORT is supplied by Render; the startup script fails if missing rather than silently binding a wrong port. No Docker or optional requirements-rag dependencies are needed. Python version selection follows [Render Python version guidance](https://render.com/docs/python-version); a real Linux/Render dependency installation has not been run by this preparation.

Set these non-secret server variables:

```text
ENVIRONMENT=production
MONITOR_ENABLED=false
AGENT_EXECUTION_ENABLED=false
AGENT_MANAGED_ENABLED=false
AGENT_MANAGED_HTTP_ENABLED=false
ENABLE_INCIDENT_MANAGEMENT=false
CORS_ORIGINS=["https://YOUR_ACTUAL_VERCEL_DOMAIN"]
```

Replace the illustrative origin with the actual assigned Vercel production origin, without a trailing slash/path. This is JSON, not a comma-separated string. The hosted entry point ignores .env files and rejects wildcard, HTTP, loopback, private-IP, credential-bearing and path-bearing origins. Multiple deliberately approved production/preview origins may be listed explicitly; do not use `*.vercel.app`. With CORS_ORIGINS unset/[], browser cross-origin access is closed while health can still be checked directly.

Do not provide DATABASE_URL, webhook/action tokens, provider keys, Qdrant credentials or model paths. They are unused by this profile. Fault-injection routes/Express services are not deployed. The disabled flags document intent; the separate entry point enforces it regardless of their values.

## Persistence and free-hosting limits

This API is **stateless**, not ephemeral SQLite marketed as persistent. No SQLite file, in-memory fake database or seeded synthetic operational database is used. Restarts retain no incidents because there are no writes or stored incidents.

Render documents that free web services use ephemeral filesystems and sleep after 15 minutes without inbound traffic. Cold starts can delay frontend requests; the UI may show unavailable/retrying until the service wakes. Do not add artificial keep-alive traffic or promise always-on service. See [Render free services](https://render.com/docs/free) and [web service ports](https://render.com/docs/web-services).

To support actual incident persistence later, provision a separately approved persistent SQL database or a persistent single-host volume with backup/restore, plus the required production authentication, ingestion secret management and worker supervision. PostgreSQL would need a tested driver/configuration/migration path; it is **not implemented or provisioned here**. Embedded Qdrant likewise requires durable single-owner storage or an explicitly supported vector service. Never point cloud deployment at the owner's local SQLite/Qdrant files. Multi-worker/replica deployment requires queue/lease/storage design beyond the local sequential worker. No free durable-storage or paid plan is promised.

## Vercel settings — hosted API mode

Use the existing frontend and repository, root `frontend`, framework Next.js, install `npm ci`, Next.js default output. `frontend/vercel.json` now runs `npm run build:vercel`:

- Default: synthetic demo, equivalent to build:demo, no backend/API requests.
- With NEXT_PUBLIC_HOSTED_API=true: real hosted-API build; requires a public HTTPS API origin and forces synthetic demo off.

For Option A set in Vercel Production (and explicitly configured Preview environments if used):

```text
NEXT_PUBLIC_HOSTED_API=true
NEXT_PUBLIC_DEMO_MODE=false
NEXT_PUBLIC_API_URL=https://YOUR_ACTUAL_RENDER_SERVICE.onrender.com
```

The URL is illustrative; use the actual Render HTTPS origin, without an API path, credentials, query or fragment. No actual URL is asserted by this preparation. The build fails rather than falling back to localhost if the hosted origin is missing/unsafe. `npm run build:hosted` is the explicit equivalent command; `npm run build:demo` remains the separate synthetic build. To switch modes/origins, rebuild: NEXT_PUBLIC values are public build-time configuration, never secret storage. See [Vercel environment variables](https://vercel.com/docs/environment-variables).

Do not merely enable NEXT_PUBLIC_HOSTED_API while retaining an old dashboard Build Command override of `npm run build:demo`: clear the override/use `npm run build:vercel` so frontend/vercel.json takes effect. Do not deploy a hosted-mode frontend before the API URL and exact CORS origin are configured.

## Deployment order and verification — not performed yet

1. Obtain separate deployment authorization and verify owner account/free-plan eligibility. Stop before any charge or paid plan.
2. Create the Render service using the settings above. Initially CORS may remain [] if the Vercel domain is not assigned; this does not grant browser access.
3. Record the **actual** Render origin. Verify its `/api/health`: healthy, mode hosted-readonly, storage stateless, database not_configured, all capabilities false. A generic 200 from a wrong local/full backend is insufficient.
4. Configure Vercel hosted mode and the real Render origin. Record the actual Vercel domain and set Render CORS_ORIGINS to that exact origin; redeploy/restart configuration as the provider requires.
5. Verify the actual cross-origin GET, using that real frontend Origin. Expect access-control-allow-origin equal to it; an unrelated Origin must receive no allow-origin header.
6. Verify frontend connection indicator from the real response and the “Hosted read-only API — stateless” banner. Incidents/history remain empty, services Unknown, knowledge unavailable and investigations disabled. No demo incident should appear. Check all seven routes, Network/Console, and that no localhost/model/privileged request occurs.
7. Try an unauthenticated synthetic POST to ingestion: expected 403, with no record created. Never send private evidence or credentials as a test.
8. Record actual URLs and results only after deployment. Deployment, remote CORS, Linux hosting and browser behavior remain unverified here.

Example read-only checks, substituting real assigned origins:

```sh
curl --fail https://YOUR_ACTUAL_RENDER_SERVICE.onrender.com/api/health
curl -i https://YOUR_ACTUAL_RENDER_SERVICE.onrender.com/api/health \
  -H 'Origin: https://YOUR_ACTUAL_VERCEL_DOMAIN'
```

## Local preservation and reproduction

Work was performed in an independent clone, with no writes to the owner's original project or home-root Git repository. Local `app.main:app`, normal local frontend defaults, stored data and model configuration remain unchanged. Hosted application code is additive; no model or service was activated for testing.

From a clone with dependencies installed, run sequentially:

```sh
(cd backend && OPSGUARD_LIVE_OLLAMA_TEST= OPSGUARD_LIVE_CODEX_TEST= OPSGUARD_RAG_INTEGRATION= .venv/bin/python -m pytest tests -q)
(cd frontend && npm test)
(cd frontend && npm run typecheck)
(cd frontend && npm run lint)
(cd frontend && npm run format:check)
backend/.venv/bin/python scripts/check-hosted-api.py
```

The process-backed runner uses temporary loopback ports and a stateless API; React performs real HTTP requests without response mocks across all seven pages. It creates no SQLite data and stops only its child. Its temporary log directory is retained. Backend tests also verify rejected writes/CORS and a fresh process with no local runtime imports or database creation. These are API/DOM checks, not screenshots or cloud deployment verification.

After normal memory pressure returns, verify builds sequentially:

```sh
(cd frontend && NEXT_PUBLIC_API_URL=https://api.example.invalid NEXT_TELEMETRY_DISABLED=1 npm run build:hosted)
(cd frontend && NEXT_TELEMETRY_DISABLED=1 npm run build:demo)
```

The `.invalid` origin is a build-only fixture, not a deployed API; do not use it for the real deployment. Tests/builds load no models. A publication-era scorer unit test that depended on an excluded evaluation export now uses a minimal inline synthetic case; no private evaluation file is reintroduced.

## Phase 5.17A verification record

- Full backend suite: **225 passed, 3 opt-in skips**. Local API/adapter/provenance suites remain intact; no real inference was run.
- Frontend suite: **50 passed, 4 process-backed cases skipped in the ordinary run**. The new hosted API process-backed case passed separately against an actual temporary FastAPI process across all seven pages, with no response mocks, writes denied and no database created. Other historical integrations were not needlessly rerun.
- TypeScript, ESLint and Prettier: passed after the final component/label edits.
- Five build-configuration checks: valid public HTTPS accepted; missing, loopback, credential-bearing and path-bearing origins rejected.
- Hosted production build and seven-route/public-asset scan: passed before the final label-only edits. **Final hosted/demo/local production build reruns remain deferred**: macOS pressure stayed level 2 at repeated gates. Do not represent this as a fresh final production-build pass. Run those gates again after memory pressure recovers before provider deployment.
- Original project source checkpoint and twelve protected SQLite/Qdrant/service hashes remained unchanged. Work and generated dependencies stayed in the independent clone; test evidence stayed in temporary directories and was not staged.
- Modified-source secret/private-path review, documentation links, blueprint settings and git diff --check passed. No model, Docker daemon, remote database, paid service or provider deployment was started. GitHub reported no linked deployments before the authorized source push.

**Remaining gates:** normal-memory final builds/asset scans; actual Render/Vercel account and free-plan eligibility; actual assigned HTTPS URLs and exact CORS origin; Linux/provider installation and remote browser/network verification. The API intentionally provides no incident persistence, live microservice monitoring, RAG or AI functionality. A real frontend-to-backend contract is verified locally, not on cloud providers.

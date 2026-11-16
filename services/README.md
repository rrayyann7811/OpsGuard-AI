# Phase 2 simulated microservices

Three independently runnable Express services share request logging, validation, controlled faults and a bounded incident publisher. See [incident simulation guide](../docs/INCIDENT_SIMULATION.md) and [incident contract](../docs/INCIDENT_EVENT_CONTRACT.md).

```sh
cd services
npm ci
npm test
# Separate terminals:
npm run start:user
USER_SERVICE_URL=http://127.0.0.1:3001 npm run start:order
ORDER_SERVICE_URL=http://127.0.0.1:3002 npm run start:payment
```

Fault injection is off by default. For a local service, prefix its start command with `NODE_ENV=development ENABLE_FAULT_INJECTION=true`. Direct Node processes bind loopback by default; containers set `HOST=0.0.0.0` and publish only loopback ports.

Docker (from this directory): `docker compose up --build -d --wait`. Stop with `docker compose down`. This stack creates no persistent volumes. Never use `down -v` to stop this project.

Data is in memory, limited to 1,000 records per process, and resets on restart. Registration and payments are simulations, with no passwords, authentication, external payment provider, or real money movement. Phase 3 dashboard cards now read real incident and health APIs.


## FastAPI publication

Export INCIDENT_INGESTION_URL and the matching INCIDENT_WEBHOOK_TOKEN before Node startup. Example URL: http://127.0.0.1:8000/api/incidents/events. Docker Desktop against the Mac host may use host.docker.internal, configured explicitly; host API bind/firewall must allow that route. See [Phase 3 demo](../docs/PHASE3_DEMO.md). Retries are bounded to three attempts with unchanged event IDs; failures are safe and delivery is best effort.

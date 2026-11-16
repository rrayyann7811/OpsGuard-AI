# Public source release inventory — Phase 5.16

Owner-approved target: https://github.com/rrayyann7811/OpsGuard-AI, public, branch main. The release uses an independent filtered source copy; the original project and inherited home-directory repository are not used for staging or publication. The owner approved the included [MIT license](../LICENSE), copyright 2026 Syed Rayyan Ali.

## Included and excluded

Included: Next.js frontend and labeled public demo, FastAPI source/tests, Express services/tests, investigation adapter source/tests, scripts, lockfiles, configuration examples, documentation and the 24 authored synthetic knowledge records. No incident-processing behavior was changed for publication.

Excluded: actual .env credentials, generated demo environments/tokens, SQLite files/sidecars, runtime Qdrant, model weights/caches, virtual environments, node_modules, Next/Vercel/build output, raw logs/evidence/evaluation exports, internal progress history and parent Git metadata. Nothing was deleted from the original project.

Only publication-copy documentation was made portable: owner filesystem/runtime paths were replaced with illustrative /path/to locations and links to intentionally omitted evidence were converted to explicit local-only references. Security-test code retains deliberate synthetic canaries and generic path-rejection examples; these are not configured credentials. No actual credential was identified by the bounded content/filename audit. Automated scanning does not guarantee absence of every possible secret.

## Verification boundary

Phase 5.15 passed 48 frontend tests (three opt-in cases skipped), TypeScript, ESLint, formatting, both webpack builds, seven prerendered demo routes and a 71-asset scan for localhost URLs, owner paths and credential signatures. Earlier local backend/service checks remain historical; publication does not invent new test results. Application source is preserved in the independent copy.

Public demo: clearly synthetic bundled examples, no API requests, Unknown/unobserved service health, no generated diagnosis, disabled semantic search/inference/privileged actions. The local full-stack mode remains available. Rendered browser QA and genuine Ollama inference remain pending. No screenshots or deployment success are invented.

## Website deployment remains separate

No Vercel deployment is part of this release. After separate owner authorization, import this repository with root frontend/, framework Next.js, install npm ci, build npm run build:demo, default output and no credentials. See [deployment guide](DEPLOYMENT_GUIDE.md). Full-stack hosting still requires durable storage, worker supervision, public security design and measured resource requirements.

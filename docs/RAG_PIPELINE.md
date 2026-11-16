# Historical incident retrieval — Phase 4

## Architecture and truth boundaries

```text
Versioned synthetic historical JSON (source documents)
 → Pydantic validation, normalization and redaction
 → structured document text
 → tokenizer-aware chunks only when necessary
 → local Sentence Transformers CPU embeddings
 → dedicated Qdrant collection (cosine distance)
 → query embedding / metadata filters / actual Qdrant scores
 → ranked, deduplicated historical sources
 → FastAPI → Next.js Historical Knowledge and incident evidence dialog

SQLite current incident → read-only evidence query → same retrieval pipeline
```

SQLite remains the source of truth for operational incidents. This phase does not change incident tables, lifecycle, ingestion or microservices. The curated historical source is `knowledge/data/incidents.json`, containing 24 original synthetic incidents (eight per service), not real operational incidents or copied company postmortems. Qdrant is its rebuildable search index. Source root causes/resolutions are authored synthetic facts, never inferred conclusions about the current operational incident. No LLM, generation, Codex agent or Phase 5 workflow is implemented.

## Model and compatibility

Model: `sentence-transformers/all-MiniLM-L6-v2`, pinned to commit `c9745ed1d9f207416be6d2e6f8de32d1f16199bf`. It produces normalized 384-dimensional vectors; collection distance is cosine. CPU execution is explicit. Model loading is lazy and guarded by a lock, and model dimension is checked. `trust_remote_code=False` and `local_files_only=True` are defaults. There are no random/hash-vector fallbacks or paid APIs.

Python 3.14.3 on macOS ARM64 was verified with Sentence Transformers 5.7.0, PyTorch 2.15.0 and qdrant-client 1.20.0. Compatible binary wheels installed without changing existing Phase 1–3 locked versions; `pip check` passed. The original backend environment was retained, not replaced. Python 3.12 is available on this machine but a fallback environment was unnecessary and is not claimed tested. On another platform lacking compatible wheels, create a separate project-local `.venv-rag` with Python 3.12 and install the RAG requirements there; do not destroy a working backend environment.

A complete model snapshot was already cached locally: weights 90,868,376 bytes (about 91 MB), plus tokenizer/config files. It loaded and encoded offline; no model assets were downloaded during implementation. For a new machine, model assets require roughly 92 MB plus Python dependencies. Obtain approval before downloading those assets. After approval, explicitly populate the pinned cache, for example:

```sh
# Only after approval; from backend/ with RAG dependencies installed:
.venv/bin/python -c 'from sentence_transformers import SentenceTransformer; SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2", revision="c9745ed1d9f207416be6d2e6f8de32d1f16199bf", device="cpu", trust_remote_code=False)'
```

Normal operation and tests do not execute that command. Missing assets produce an actionable 503 from retrieval while incident monitoring remains available. Python package downloads (including PyTorch) are separate from model weights and consume additional disk space.

Model sources: [official model card](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2), [Sentence Transformers installation](https://www.sbert.net/docs/installation.html).

## Qdrant modes

Default: the official Python client's **persistent local mode**, using `QdrantClient(path=...)`. This is embedded storage in the FastAPI process, not a running Qdrant server, HTTP endpoint, container, or cloud service. Status reports `embedded-local`. It is appropriate for this small development dataset and integration tests. Only one process may hold a persistent path at a time; use one Uvicorn worker and stop the API before indexing/evaluating that same path. Thread access is serialized within the application. Another holder of the path is reported as unavailable/locked.

QDRANT_URL switches to a real server connection and overrides QDRANT_PATH. QDRANT_API_KEY is server-only. Server mode has a three-second client timeout; its runtime connectivity is not verified in this environment. Docker is still unavailable and was not installed. [Official local-mode documentation](https://github.com/qdrant/qdrant-client) describes the supported development option.

| Variable | Default |
| --- | --- |
| QDRANT_URL | Empty: persistent embedded-local mode |
| QDRANT_PATH | Absolute project-derived `knowledge/.qdrant` |
| QDRANT_API_KEY | Empty; do not expose in frontend variables |
| QDRANT_COLLECTION | opsguard_history_v1 |
| EMBEDDING_MODEL | sentence-transformers/all-MiniLM-L6-v2 |
| EMBEDDING_REVISION | Pinned 40-character commit above |
| EMBEDDING_DIMENSION | 384 |
| EMBEDDING_LOCAL_ONLY | true |

Qdrant URLs must be HTTP(S) without embedded credentials/query. An existing collection must have matching vector size and cosine distance; incompatible collections are rejected, never recreated. Changing models/revisions changes the model identity filter and invalidates embedding reuse; use a new dedicated collection name when changing geometry or comparing models. Existing foreign points are protected against overwrite. There are no delete/recreate operations.

## Dataset and processing

Each record includes id, title, service_name, symptoms, error_type, error_message, root_cause, resolution, technology, severity, incident_date, source_ref, runbook, code_context, http_status and `synthetic: true`. IDs follow SYN-USR/ORD/PAY-NNN. Input fields and lengths are validated, unknown fields rejected, and duplicate source IDs rejected before indexing starts. Text is Unicode-normalized, whitespace-normalized and redacted using the existing credential redaction boundary. No raw incident request bodies are indexed.

Preparation retains structured symptoms/error/cause/resolution/steps/technology/code context. Source metadata is retained in the payload. Short records stay as one chunk; all 24 current records fit one chunk each. Longer documents use tokenizer boundaries below the 256-token model budget, with 24-token overlap. Point UUIDs are deterministic from source ID and chunk number. A hash includes source content, model commit, dimension and text preparation version. Unchanged sources skip embedding and upsert entirely.

Indexing first computes valid embeddings before changing the source's currently searchable chunks. Old chunks are marked inactive, replacements are upserted inactive, and only successfully written replacement IDs become active. Old extra chunks are retained inactive, not deleted. A failed write can temporarily make that source unavailable until rerun; no atomic whole-dataset snapshot is claimed. A failed embedding leaves the previous searchable source unchanged. Records omitted from a later source file are not automatically purged. Partial batches are recoverable by rerunning; unchanged complete sources are reused. This favors non-destructive development indexing over complex migration infrastructure.

Payloads contain owner/model identifiers, document/chunk IDs, content hash, service/severity, indexed_at, chunk text and the attributed historical document. The index does not replicate the operational incident-management schema. Status counts distinct active source IDs, active chunks and distinct source references for the selected model; last_indexed_at is the latest successful document indexing timestamp, not an assertion that every attempted batch succeeded.

## Commands without Docker

```sh
cd backend
# Adds the optional full pinned RAG stack; base lock remains unchanged.
.venv/bin/python -m pip install -r requirements-rag.lock.txt
# Stop any API using the same local Qdrant path before indexing.
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 .venv/bin/python -m app.knowledge_cli index
# Repeat: reports indexed=0, unchanged=24 on an unchanged dataset.
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 .venv/bin/python -m app.knowledge_cli status
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

In another terminal, from frontend/: `npm run dev` (or `npm run dev -- --webpack` for the known environment-specific Turbopack permission issue). Open /knowledge. Search for `Payment fee was subtracted instead of added to the total`. Inspect the actual score and source record. Select a real current incident and click **Find Similar Historical Incidents** for a read-only SQLite-driven search.

With Docker available, optionally run a loopback-bound Qdrant server and configure QDRANT_URL. Use the same Python indexing/search code; local mode is not a substitute claim for server/container verification. No Docker image was pulled or server started here. Do not reuse/delete unrelated collections or volumes.

## APIs

| Method | Endpoint | Behavior |
| --- | --- | --- |
| GET | /api/knowledge/status | Collection/mode/counts/model configuration/load state/indexing timestamp |
| GET | /api/knowledge/incidents | Paginated indexed sources; service/severity filters |
| GET | /api/knowledge/incidents/{id} | Full attributed historical source |
| POST | /api/knowledge/search | Validated query, top_k 1–10, service/severity, min_score -1–1, semantic ranking |
| POST | /api/knowledge/similar/{operational-incident-id} | Read existing SQLite evidence and retrieve history; never changes the incident |

```sh
curl -s http://127.0.0.1:8000/api/knowledge/status
curl -s 'http://127.0.0.1:8000/api/knowledge/incidents?page=1&page_size=6&service=payment-service'
curl -s http://127.0.0.1:8000/api/knowledge/incidents/SYN-PAY-004
curl -s -X POST http://127.0.0.1:8000/api/knowledge/search -H 'Content-Type: application/json' -d '{"query":"Payment fee subtracted instead of added", "service":"payment-service", "top_k":3, "min_score":0.3}'
# Replace with a real operational ID; body may be {}:
curl -s -X POST http://127.0.0.1:8000/api/knowledge/similar/ACTUAL-INCIDENT-UUID -H 'Content-Type: application/json' -d '{}'
```

Responses include actual cosine similarity, separate rank_score, matched_chunk, full historical source, source_ref, timing, ranking method and an evidence disclaimer. No-match is a successful response with items=[]; invalid payloads return 422, missing sources/incidents 404, and Qdrant/model failures 503. Query size is capped at 6000 characters and existing 32 KiB body limits apply. Long queries embed all token-bounded chunks and normalize their average vector; noisy stack traces can dilute that pooled representation. Service/severity filters run in Qdrant before scoring. Candidate chunks are collapsed to their highest-scoring source and sources sorted by actual scores. At most 100 candidates are considered, sufficient for this dataset but not a scale guarantee.

The UI uses threshold 0.3; API defaults are 0.25 unless supplied. Similarity scores are not probabilities. A minimum score cannot guarantee relevance. See [evaluation](RAG_EVALUATION.md). The experimental hybrid heuristic showed no measured quality gain and is available only to the evaluation code, not the public API/UI. Semantic-only remains the supported ranking.

## Security and testing

No HTTP index mutation endpoints exist. Indexing is an operator-run local CLI restricted to ENVIRONMENT=development. Read/search routes follow the project's local-only exposure boundary; user authentication and production access controls are not added. Trusted configured CORS origins may now send search POST requests. Webhook ingestion still requires its server-only token. No Qdrant/model credentials belong in NEXT_PUBLIC configuration. Synthetic historical content is never treated as instructions to execute code.

```sh
# backend/: deterministic local-Qdrant tests; no model asset downloads
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 .venv/bin/python -m pytest -q
# Opt into real cached model + persistent Qdrant test:
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 OPSGUARD_RAG_INTEGRATION=1 .venv/bin/python -m pytest -q
# root/: actual model/Qdrant/FastAPI/React DOM pipeline
backend/.venv/bin/python scripts/check-knowledge-pipeline.py
# Original real Node incident pipeline:
backend/.venv/bin/python scripts/check-incident-pipeline.py
```

Routine interface tests use explicitly labeled deterministic test vectors, not semantic quality assertions. The opt-in integration uses actual cached embeddings and persistent local Qdrant, reopens its store, and checks real retrieval. The UI integration uses real HTTP responses and validates search, source detail, and similar-incident lookup with unchanged operational status. Integration runners use owned temporary directories and leave the normal SQLite database/index intact. DOM integration is not full browser visual QA.

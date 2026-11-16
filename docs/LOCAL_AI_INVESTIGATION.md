> Phase 5.12: website/readiness completion uses deterministic checks only. The additive `GET /api/investigations/readiness` separates model configuration, server connectivity, installation and the unchanged memory guard. It never loads a model or authorizes inference. Real inference remains pending. See [website startup and later manual checklist](WEBSITE_OWNER_TESTING.md). Existing private environment files were not overwritten.

# Local AI investigation — Option B

2026-11-15: **Implemented — live local inference pending; Phase 5.11 preflight blocked by insufficient memory.** The selected backend is `local-ollama`. Managed adapters/tests and the blocked local Codex adapter are preserved, but managed execution stays disabled. No cloud inference, model download, persistent model/configuration modification or genuine local inference occurred. Phase 5.11 briefly started the explicitly authorized existing daemon for read-only checks, then stopped it gracefully. Phase 6 has not begun.

## Phase 5.11 — current verified runtime and blocker

The authorized existing daemon successfully started on numeric loopback with cloud features disabled. Installed inventory is now known: `llama3.2:3b` (2,019,393,189 bytes, Q4_K_M) and `llama3:latest` (4,661,224,676 bytes, Q4_0). The 3B model is the lightweight candidate; the 8B model exceeds the unchanged file-size ceiling. The actual adapter preflight rejected the 3B model with `OLLAMA_MEMORY_INSUFFICIENT`: required estimate ~3.32 GiB versus sampled reclaimable estimates ~2.02–2.04 GiB. Normal macOS pressure does not override this load-headroom check. No model loaded or generation request was sent, and no limit was relaxed.

The owned daemon is stopped again. No actual report, diagnosis, model timing/memory or real-report UI verification exists. Fresh ordinary regressions passed; they remain separate from real reasoning. See Phase 5.11 evidence and limits (local-only reference; not included in this release) and machine-readable results (local-only reference; not included in this release). More fresh headroom, including after RAG initialization, is required before a controlled real investigation can proceed. Phase 5.12 has not started. The older startup/model-unknown observations below describe Phase 5.10 history, not the current inventory.

## Runtime check and model selection

Read-only checks found Ollama **0.16.3** installed. Inside the Codex workspace sandbox the CLI crashed during Metal/MLX initialization. The separately authorized read-only check outside that sandbox reported the client version and that no Ollama server was running; `ollama list` failed for that reason. It also warned that the MLX dynamic library was unavailable. No daemon was started and no models were inspected through private files. **Installed model inventory and the best installed model are unknown**, not an empty inventory. Resolve runtime/library availability before a real trial.

Select an already installed, local GGUF text/chat model explicitly after the owner starts Ollama. The adapter requires the exact `/api/tags` name, digest, positive size and GGUF format, rejects remote/cloud metadata and cloud-named models, and limits on-disk size to 2.5 GB by default. A small quantized 1–3B-class model is the resource target, not a claim that any particular model is installed, compatible or accurate. Structured-output capability, model context and useful reasoning must be verified for the selected model. No model is silently selected, pulled or replaced.

Official interface references, checked 2026-11-15: [chat](https://docs.ollama.com/api/chat), [installed models](https://docs.ollama.com/api/tags), [loaded models](https://docs.ollama.com/api/ps), [structured outputs](https://docs.ollama.com/capabilities/structured-outputs), [runtime parameters](https://docs.ollama.com/modelfile), [official request option types](https://github.com/ollama/ollama/blob/main/api/types.go), [local FAQ](https://docs.ollama.com/faq). The application reuses installed httpx; no Ollama SDK or dependency installation is needed.

## Setup and authorization

The application works without AI: leave `AGENT_EXECUTION_ENABLED=false` and the model blank. Incident ingestion, service monitoring, SQLite history, Qdrant retrieval and the dashboard continue independently. No fake diagnosis is generated when AI is disabled.

Only after explicit authorization to start Ollama and perform inference, the owner should start their existing runtime bound to loopback. Do not expose it on `0.0.0.0`, enable a tunnel or point the application to a cloud proxy. No startup or installation command is run by OpsGuard. The owner should independently verify the runtime is local-only; the application does not modify Ollama's configuration. Set backend-only values (placeholders below are instructions, not installed configuration):

```text
AGENT_EXECUTION_BACKEND=local-ollama
AGENT_EXECUTION_ENABLED=true
AGENT_AUTH_TOKEN=<dedicated local action token>
AGENT_OLLAMA_URL=http://127.0.0.1:11434
AGENT_OLLAMA_MODEL=<exact already-installed local model:tag>
AGENT_MANAGED_ENABLED=false
AGENT_MANAGED_HTTP_ENABLED=false
```

The URL must be HTTP with numeric `127.0.0.1` or `::1`, an explicit port and no credentials, path, query or fragment. DNS hostnames, public endpoints, redirects and inherited HTTP proxies are rejected/disabled. Never use Ollama cloud models. No provider key or paid authorization is required. Keep action tokens out of NEXT_PUBLIC, source, logs and browser storage. Existing credential values were not configured by this work.

Run one FastAPI worker on loopback using the existing README startup procedure. Open a persisted incident and choose Investigate with AI. The UI displays model readiness/name and requests authorization for **one Local AI Investigation**, not paid API usage. Backend actions still require a loopback development client and the dedicated action token. The additive request is:

```text
POST /api/incidents/<persisted incident UUID>/investigate
Authorization: Bearer <dedicated local action token>
Content-Type: application/json

{"authorize_local_execution":true}
```

Paid-only authorization is rejected for this backend. Legacy Codex/managed/test-double request contracts remain supported for their explicitly selected backends. There is no automatic fallback to those adapters.

## Local pipeline and evidence boundary

The existing worker reads the actual incident and recent events from SQLite, performs bounded historical retrieval through the existing local embedding/Qdrant components, reads approved source excerpts and collects scoped Git history. It preserves the existing states, IDs, progress events, persistence and report routes. No schema migration or Qdrant rewrite is needed.

`RepositoryReader` remains the only source/Git inspection implementation. It limits JS/TS reads to `services/shared`, `services/fixtures` and the affected service; rejects traversal, symlinks, hidden/environment files and unsupported files; and uses fixed read-only Git operations with deadlines. The inherited home Git repository remains prohibited. Missing source, history or Git is an explicit limitation, never an invented result.

The adapter receives a data bundle, not a repository path or filesystem handle. It reuses the existing evidence schema, path checks, secret redaction and residual-sensitive-content rejection. URLs/IPv4 addresses in content are redacted as additional data minimization. Known instruction-injection patterns in logs/source/Git/history are rejected. Every evidence field is treated as untrusted data; the system instruction cannot grant it authority. Pattern matching cannot detect every semantic prompt attack. The decisive boundary is that the model has **no tools or action executor**, and its output is never passed to a shell, Git command, file writer or URL fetcher.

Raw input is bounded to 128 KiB. The model prompt contains the existing report schema and a bounded subset of actual evidence. Selection prioritizes the persisted incident, relevant sources, scoped Git changes and history; excess items are omitted whole, with limitations, preserving IDs/ranges/hashes. It does not invent abridged evidence or renumber citations. A model cannot cite omitted items even if they remain visible in the application's collected-evidence view. `submitted_evidence_ids` records the exact subset in execution metadata.

Generation uses only `POST /api/chat`, explicit JSON schema format, nonstreaming output, temperature zero, bounded context/output, two CPU threads and `keep_alive=0`. It supplies no tools, environment variables, files, credentials or remote functions. `GET /api/tags` and `/api/ps` perform preflight checks without loading a model. Only read-only availability requests retry once; generation is never retried automatically. Ollama is a trusted local inference daemon, not a verified OS sandbox; no Codex containment restriction is bypassed or relaxed.

## Validation and provenance

The returned assistant JSON must satisfy `AgentAnalysis`. Required fields, known evidence IDs, source ranges, collected commit SHAs and retrieved history IDs are checked. Unknown citations, omitted-evidence citations, fabricated paths/commits, malformed/truncated responses, tool calls, patches and code blocks are rejected. Invalid output becomes a persisted failure, not a replacement test-double report.

A valid uncertain answer returns an explicit insufficient-evidence confidence category. With no evidence records the run fails rather than inventing a citation. Other confidence categories are application-computed evidence coverage, not probability; no fabricated percentage is shown. A hypothesis is never upgraded to verified causality by model wording. Semantic truth still requires human review.

Genuine production-path output uses backend/mode `local-ollama`, provider `ollama` and the actual selected model/digest. Any injected HTTP transport is conservatively labeled `test-double`, provider `deterministic-ollama-test-double`, and the report carries a TEST DOUBLE limitation. Local Ollama results are never labeled Codex. The UI displays **Local AI Investigation**, model, evidence/timeline, report/references/limitations, actual total duration, prompt/output bytes and measured response time.

## Resources, cancellation and recovery

| Control | Default |
| --- | --- |
| Concurrent inference | One per adapter; one sequential worker per application, single backend process required |
| Job / local analysis deadline | 90 / 60 seconds |
| Read-only probe retries | One; no generation retry |
| Prompt / accepted output ceiling | 24 KiB / 16 KiB; response envelope bounded separately |
| Context / generated tokens | 8,192 / 1,536; generated-token maximum configurable up to 2,048 |
| Effective prompt admission | Further reduced by a conservative UTF-8 byte budget, output reserve and 512-token overhead reserve |
| Model on-disk ceiling | 2.5 GB; never a guarantee of total RAM usage |
| Memory admission | Estimated available memory at least 2 GiB and estimated load headroom (`1.5 × model size + 512 MiB`, adjusted for already loaded model) |
| During-generation safety check | Poll estimated available memory every 0.5 seconds; stop the HTTP request below 512 MiB or if measurement is unavailable |
| Other loaded Ollama models | Refuse inference; never unload another user's model |
| Retention request | `keep_alive=0` requests unloading after completion |

Byte admission is intentionally conservative and can reduce context enough to hurt diagnosis. It is not a tokenizer certification or strict GPU/RAM quota. RAG embeddings also consume shared RAM. Do not run local evaluation alongside builds, Docker workloads or another model. Other clients must not use the same daemon concurrently; the application cannot reserve the daemon globally.

Metrics record prompt/output bytes, wall-clock inference and adapter duration, backend lifetime peak RSS, host available-memory estimates before/after, any preloaded model size, and available Ollama timing/token counters. Ollama timing values are nanoseconds; wall-clock values are milliseconds. No memory value is presented as a per-investigation GPU peak. Missing counters stay absent, not fabricated.

Cancellation closes/cancels the owned HTTP operation; there is no claimed daemon-wide cancellation API or proof that compute immediately stopped. Timeouts, transport ambiguity, response-limit interruption or memory pressure after submission block more local jobs and persist stop state. On restart, unfinished investigations become FAILED/BACKEND_RESTART, never resume automatically, and uncertain local execution remains blocked.

An operator must independently inspect/stop the generation and unload it. After all jobs are terminal and Ollama is reachable with **no loaded models**, the authenticated local operator may explicitly reconcile:

```text
POST /api/investigations/runtime/acknowledge-stop
Authorization: Bearer <dedicated local action token>
Content-Type: application/json

{"confirm_runtime_stopped":true}
```

This performs a read-only `/api/ps` check, records reconciliation and never restarts inference. It rejects a busy/unreachable daemon and requires a real boolean. The endpoint cannot independently prove no other client will start new work; operate a dedicated local runtime and one backend worker.

## Controlled demonstration — not run with a real model

The existing Phase 5 runner now has a separately gated local mode. Before running it, explicitly authorize real local inference, start/check the existing runtime and select a suitable installed model. No downloads or daemon startup occur in the runner:

```sh
# Future authorized run only, from project root. May load the selected local model.
OPSGUARD_LIVE_OLLAMA_TEST=I_AUTHORIZE_LOCAL_INFERENCE \
AGENT_OLLAMA_MODEL='<exact installed model:tag>' \
backend/.venv/bin/python scripts/check-investigation-workflow.py --local-ollama
```

It prepares disposable SQLite/Qdrant/Git fixtures through existing tooling, starts actual loopback backend/payment processes, triggers the controlled faulty-commit failure, observes ingestion and actual collection/retrieval, asks the selected local model once, validates/persists the report and tests React against the real API. Original stores/source remain untouched; temporary fixture commits are not project commits. All child application processes are cleaned up. A failed model/report check fails the demo; it never substitutes fake reasoning. The no-authorization branch was checked and refused before starting anything.

The opt-in adapter test is separate:

```sh
# Future authorized run only, runtime already running; not part of ordinary pytest.
cd backend
OPSGUARD_LIVE_OLLAMA_TEST=I_AUTHORIZE_LOCAL_INFERENCE \
OPSGUARD_OLLAMA_TEST_MODEL='<exact installed model:tag>' \
.venv/bin/python -m pytest tests/test_ollama.py -k opt_in_real -q
```

## Evaluation methodology and verified results

Use the existing ten controlled cases in `evaluation/investigation_cases.json`, one case at a time. Preserve actual API investigation snapshots and selected model/digest, duration, evidence and failure codes. Ground truth stays outside the model prompt. Historical references may nevertheless reveal similar causes, so label the experiment as evidence-assisted analysis, not blind benchmarking.

`evaluation/local_ai_evaluation_plan.json` deliberately stores **null** metrics because real evaluation has not run. `scripts/evaluate-local-investigations.py` scores saved responses only and never calls a model. Its input entries contain `case_id`, `investigation` (the detail response's investigation field) and optionally `review: {root_cause_correct: boolean, reviewer: string}`. It rejects test-double provenance. Write a new results file:

```sh
backend/.venv/bin/python scripts/evaluate-local-investigations.py \
  <saved-genuine-local-results.json> <new-evaluation-output.json>
```

Report manual root-cause identification accuracy against known ground truth, exact expected affected-file accuracy, report citation-validation pass rate, measured mean duration and error rates. Automated expected-term matching is only a heuristic; missing manual review yields null root-cause accuracy. Operational/model-or-timeout error rates include preflight/validation failures and are not pure model-engine failure rates. Small case counts and shared synthetic history limit generalization. Caller-supplied saved provenance still needs independent audit.

Current deterministic results and read-only resource diagnostics are recorded in verification results (local-only reference; not included in this release). Backend tests include configuration, loopback/cloud/model/memory guards, valid and malformed JSON, missing/omitted/fabricated evidence, prompt limits/redaction/injection rejection, bounded retries, timeouts, cancellation/concurrency, persisted API output/failures, restart recovery, explicit reconciliation and provenance. Routine tests deny real socket connections for the new Ollama adapter. The real-model test is skipped by default.

**No real-model accuracy, response duration, memory peak or completion claim is available.** The next step is an explicitly authorized local runtime/model/memory check and then a controlled local demonstration; Phase 6 remains out of scope.

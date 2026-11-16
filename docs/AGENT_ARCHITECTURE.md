> Phase 5.12 adds read-only readiness diagnostics and website usability without changing model execution permissions, memory thresholds or the report/lifecycle contracts. Readiness may inspect a manually running loopback daemon while execution is disabled; only explicit start authorization can invoke analysis. Diagnostic mocks identify as TEST DOUBLE, and no configured/preflight status implies live verification.

# Selected architecture — fully local Ollama analysis

The owner selected Option B. `local-ollama` is now the default backend; execution remains opt-in. Status: **Implemented — live local inference pending.** The local Codex sandbox stays blocked and unchanged. Managed adapters/tests are preserved, disabled and not selected.

The existing incident/events → Qdrant context → restricted read-only source/Git collectors → sanitized evidence-ID bundle → adapter → strict report validator → SQLite → Next.js pipeline is reused. Ollama receives bounded text through numeric-loopback `/api/chat` with the report JSON schema; no tool, repository mount, shell, file writer or external connector is provided. There is no failure fallback. Model uncertainty produces insufficient evidence; fabricated citations fail validation. Confidence is application-computed evidence coverage.

`backend/app/ollama_adapter.py` implements installed-local-model preflight, memory/context/output limits, one active inference, timeouts, read-only retries, best-effort HTTP cancellation and honest fake/real provenance. `investigations.py` adds `authorize_local_execution` without breaking preserved paid-backend contracts. Existing report routes/tables are unchanged. Unknown execution after cancellation/restart blocks new work until an authorized operator checks the idle runtime and explicitly reconciles. UI shows Local AI Investigation, model and measured timing rather than Codex or invented percentages.

See [complete local implementation and limits](LOCAL_AI_INVESTIGATION.md) for configuration, resource measurements, lifecycle, demo and evaluation. The following sections document the preserved historical Codex implementation and are not instructions to enable it.

# Phase 5 agent architecture — Implemented — live Codex verification pending

## Actual execution boundary

```text
Authorized local POST + explicit paid-use confirmation
 → SQLite investigation QUEUED (one active job per incident)
 → lifespan-owned asynchronous worker
 → persisted incident/events
 → existing Phase 4 KnowledgeStore (supporting historical context)
 → application-controlled read-only source/Git collectors
 → bounded, sanitized, evidence-ID bundle
 → official @openai/codex-sdk 0.169.0 adapter
 → disposable workspace + required native macOS sandbox gate
 → one structured Codex turn, only when all gates pass
 → strict schema and provenance validation
 → SQLite report/events → polling React UI
```

No source edits, patches, execution of repository code by the agent, automatic remediation or incident resolution are implemented. Application tools collect evidence deterministically; Codex receives that bundle rather than choosing arbitrary host commands. This is a bounded one-turn evidence-analysis agent, not an unrestricted terminal agent or iterative patch author.

**Live execution did not run.** The non-AI containment probe terminated with SIGABRT before its allowed sentinel read succeeded. The gate therefore reports unavailable and prevents model execution. A probe failure does not establish that the policy is enforced successfully. Do not bypass it, relax to full host access, or claim live reasoning passed. The pre-SDK sandbox bootstrap failure remains unresolved; final audit diagnostics below narrow the blocker without bypassing it. Docker and full browser visual QA also remain pending.

## Verified official interface

Installed project-local `@openai/codex-sdk` **0.169.0**, with its pinned native Codex CLI dependency. Verified the installed declaration files and official SDK source: `new Codex({ apiKey, env, codexPathOverride, config })`, `startThread({ workingDirectory, sandboxMode, approvalPolicy, webSearchMode, networkAccessEnabled, model, skipGitRepoCheck })`, and `thread.run(prompt, { outputSchema, signal })`. Results use finalResponse, items, usage and thread.id. No invented methods or API calls are used.

References: [official SDK guide](https://developers.openai.com/codex/sdk/), [official SDK source/README](https://github.com/openai/codex/tree/main/sdk/typescript), [SDK options](https://github.com/openai/codex/blob/main/sdk/typescript/src/codexOptions.ts), [thread options](https://github.com/openai/codex/blob/main/sdk/typescript/src/threadOptions.ts). This SDK wraps the CLI and exchanges JSONL events. Reading package types/help/version did not invoke a paid model.

This application deliberately requires a dedicated AGENT_CODEX_API_KEY and configured AGENT_CODEX_MODEL. It does not inherit the user's logged-in Codex account, ~/.codex configuration, MCP servers, hooks or auth files. OpenAI model/account availability is unverified; no particular model is silently selected. Configure an actually available Codex model for your account only after authorizing paid use.

## Repository and command controls

Default authorized project root is derived from this repository. Source scope is services/shared, services/fixtures and the affected user/order/payment-service directory. Only bounded JS/TS source files are read; environment/config credentials, hidden paths, node_modules, parent traversal and symlinks are rejected. Reads walk directory descriptors with O_NOFOLLOW to resist intermediate symlink escapes. Excerpts preserve actual line numbers, including when redacting multiline private-key material. Each source excerpt includes its path/range and original content hash. Stack traces identify candidates but never directly authorize arbitrary paths.

Git uses fixed argument lists, no shell strings. Only log/show/diff/blame/status, with scoped source paths, bounded output, four-second per-command deadlines, disabled hooks/fsmonitor/external diff/textconv/signature display/pagers, isolated global/system configuration and noninteractive execution. Stdout and stderr are captured separately so host warnings cannot become fabricated Git data. Commit hashes come from actual Git output and are checked before reuse.

A project's .git must be a normal in-root directory, with no symlinks, include/worktree indirections or object alternates. Metadata symlinks are rejected before configuration contents are opened. The current project inherits a Git repository rooted at /path/to/parent-home; that parent repository is deliberately rejected, not inspected for history. Missing history appears as a limitation. Safe fixtures create actual commits in newly owned disposable directories and never modify the original project's Git history. Git metadata/path restrictions intentionally exclude linked worktrees and some complex repository layouts.

## Planned live containment and current blocker

The SDK launcher uses a fresh HOME/CODEX_HOME/TMPDIR and a sanitized evidence-only workspace. It forwards only explicitly controlled environment values plus the dedicated API key needed by the trusted CLI. Model instructions disable tools and treat all logs/source/Git/RAG content as untrusted data. Tool feature flags, disabled web search/MCP/plugins/hooks and approvalPolicy=never are defense in depth, not the primary containment guarantee.

The required macOS deny-default sandbox policy is designed to permit reads of the sanitized workspace and minimal runtime resources, writes only under disposable runtime home/tmp, and process execution only of the pinned native CLI. Original repositories are not granted. Child shell/code-host execution and workspace edits are intended to be denied. Network access for the trusted provider transport is distinct from model tool access. Unexpected command/file/MCP/web-search items cause report rejection.

Before any paid turn, a non-AI self-test must prove allowed evidence read, denied outside sentinel read, denied workspace write, denied child execution and successful native --version. **That self-test fails on this host with SIGABRT**, so live execution is blocked even if credentials are supplied. The profile is not presented as validated protection. Other OS/architecture combinations are unavailable until an equivalent tested containment adapter is implemented. A disposable workspace alone is not considered sufficient host isolation.

## Lifecycle and limits

States: QUEUED → COLLECTING_EVIDENCE → RETRIEVING_CONTEXT → INSPECTING_CODE → ANALYZING_GIT → GENERATING_REPORT → COMPLETED; failures/cancellation terminate explicitly. Same-stage tool-audit events are permitted; skipped active stages are rejected. A partial unique SQLite index prevents concurrent active investigations for the same incident. Queue capacity defaults to 8 (maximum 20); a single lifespan-owned worker runs sequentially.

On startup, unfinished rows become FAILED/BACKEND_RESTART and are never automatically resumed or marked completed. Graceful shutdown cancels an active job; queued leftovers fail on next startup. This local implementation expects one backend worker. It is not a distributed queue, durable process supervisor or multi-worker lease system.

Total job timeout defaults to 90 seconds (5–180 configurable). Git commands use four-second limits and 64 KiB output caps. The evidence bundle is capped at 70 items/110 KB, SDK input at 180 KB and output at 128 KiB. Node heap is bounded to 256 MB; POSIX CPU/file-descriptor/file-size/core-dump limits apply. These are practical limits, not a universal memory containment claim for all native descendants. Cancellation/timeout kills the owned SDK process group. A request already sent to the provider may still incur usage; cancellation cannot promise billing reversal.

RAG is attempted at most twice, with a bounded short retry; unavailable context becomes a limitation. The application submits at most one agent turn and does not automatically retry paid investigations. Native CLI unbounded connection retries are disabled, and the total deadline bounds transport activity. CPU-based evidence collection runs through thread offloading; short SQLite lifecycle writes remain local synchronous transactions. Cancelled thread-based collection may finish its bounded read operation; no later paid turn should begin after cancellation.

## Persistent schema

Added investigations (UUID id, incident foreign key, service, status, created/start/complete times, duration, safe error code/message, collected evidence JSON, execution metadata JSON, validated report JSON) and investigation_events (ID, investigation foreign key, timestamp, state, safe event message). Existing incident/event models are unchanged. Startup creates additive tables; it does not delete incidents or Qdrant data. Evidence is retained even when no report is accepted. SQLite reserved write locks serialize status updates, completion/failure and cancellation before reading current state, preventing a concurrent audit write from reviving a cancelled job.

## Report and confidence

AgentAnalysis is strict with extra fields forbidden at every object. Findings distinguish verified_fact, hypothesis, uncertain and recommendation and require evidence IDs. Root cause must be hypothesis/uncertain. Affected paths and ranges must match collected source evidence; commits must match actual Git evidence; historical references must match supplied IDs and use server-preserved cosine/source metadata. Unknown inline paths/file basenames/hashes and unchecked numerical code references are rejected. Model-produced report text is redacted again before acceptance/storage. Generated patch/code blocks are rejected. The displayed error summary is derived from stored incident evidence.

Reports include investigation/incident/service IDs, error summary, suspected cause, explanation, verified observations, affected source ranges, suspected commits, supporting logs, historical references, conceptual remediation, limitations, execution mode and measured duration. No arbitrary confidence percentage is accepted.

Confidence categories are application-computed **evidence coverage**, not calibrated probability:

- MEDIUM: root hypothesis cites both collected source and observed log evidence; causality remains unverified.
- LOW: source is cited but observed failure evidence is not cited by the hypothesis.
- INSUFFICIENT_EVIDENCE: hypothesis lacks a collected source citation.
- HIGH: reserved for independent controlled causal reproduction; read-only Phase 5 never assigns it.

Provenance/range validation cannot prove semantic entailment or root-cause correctness. A model can misinterpret real evidence; reports retain that limitation. Historical synthetic causes are supporting context, never proof of the present incident. No reproduction, hotfix or code modification is performed by the agent.


## Final audit diagnostics and verified boundary

Read-only inspection verified installed SDK declarations, native Mach-O architecture/dependencies and public macOS policy definitions. The public system profile distinguishes file-map-executable from file reads. One changed synthetic sentinel probe added executable mapping only for the selected executable and existing public runtime directories; deny-default, scoped reads/writes and child-exec restrictions remained intact. Even that allowed /bin/cat read terminated with SIGABRT and no stdout/stderr. No further unchanged probe retries were performed. The candidate policy change was not adopted as verified containment.

This places the observed failure before SDK/model invocation and rules out an exclusively SDK-specific explanation. It does not conclusively distinguish OS sandbox bootstrap restrictions from another missing restricted-runtime permission. Strict signature checks initially failed in the restricted tool context, but all four binaries (cat, sh, sandbox-exec, pinned native Codex) verified successfully in the approved diagnostic context. No binary was re-signed/replaced and no host security control was disabled. No private user directory or credentials were inspected for diagnosis.

Live configuration still fails closed. A failed runtime probe is cached for that adapter until backend restart; routine five-second UI polls do not repeatedly retry the unchanged host failure. Positive readiness may refresh, and each explicitly authorized SDK call still rechecks containment. The status object explicitly distinguishes unverified containment. The normal no-credentials adapter test exits before any host probe.

Confirmed audit fixes: Git symlink validation now precedes config reads; descriptor reads require a bounded regular file; report text is redacted and unknown inline basenames rejected; cancellation/status writes are serialized; test-double timeline messages explicitly say TEST DOUBLE rather than claiming a Codex turn. A concurrent cancellation regression, malformed report tests and negative-readiness-cache test passed.

Application-level source/Git restrictions and report validation are tested. Actual SDK execution, sandbox enforcement and provider-side cancellation remain unverified. Passing policy-string unit tests is not evidence that the OS sandbox works. Production user authorization, multi-worker coordination, complete semantic truth verification and full browser visual QA remain outside the verified boundary.

## Phase 5.8 — explicit offline execution backends

The Phase 5.6C local Linux namespace denial remains the current local blocker; earlier Docker-unavailable statements above are historical. Phase 5.8 does not retry or weaken local containment.

The worker now selects an adapter through `execution_backends.create_adapter`: local-codex (existing implementation/default), managed-codex (offline, disabled, no transport), or explicit test-double. Selection is stored in existing investigation execution_metadata at enqueue time and checked before collection; backend drift fails rather than falling back. Existing tables, investigation endpoints, statuses, source/Git reader and Qdrant retrieval are preserved.

The managed path adds a strict synthetic evidence export builder and replaceable async session client port. Exact operator-approved digest, service/path/type/provenance validation, redaction and separate raw/export UTF-8 limits precede create. The exporter never reads paths or uploads files. It retains canonical evidence IDs and original source hashes and adds redacted-content hashes. See [managed plan](MANAGED_AGENT_EXECUTION_PLAN.md#11-phase-58--implemented-offline-application-boundary) for schema and approval semantics.

One investigation is submitted with session creation. Polling requires an explicit completed-turn observation, then bounded result retrieval/schema/provenance validation. Errors, unsupported actions and malformed reports fail. On failure, timeout or cancel, the port requests cancellation and deletion under a cleanup deadline. Pending/unknown cleanup blocks admission. Durable metadata merges retain session IDs and cleanup state after terminal jobs; startup reconciles them without recreating a turn. A database failure does not prevent best-effort cleanup of a known session. Unknown creation outcomes cannot be automatically retried.

Only injected deterministic managed clients can run in this phase. Production selection of managed-codex reports unavailable even if enable flags are set, because there is no network implementation or verified live policy. An injected simulation identifies as TEST DOUBLE in configuration, events, stored report and frontend. Real local mode is live-codex; reserved real managed mode is live-managed-codex; unknown modes display EXECUTION UNVERIFIED. No real managed report has been generated.

Limits: one investigation/session; configurable bounded in-process concurrency; evidence/output byte limits; managed and existing job deadlines plus bounded cleanup; usage recording. These do not enforce a remote billing cap or guarantee remote termination. The system still expects a single backend worker. Live SDK/event mapping, account/data/cost approvals, strict provider permissions, remote resource enforcement and actual sandbox verification remain gates. No API/billing credential configuration or external call is implemented in Phase 5.8.

## Phase 5.9 — mocked HTTP transport readiness

The managed client now has a typed REST implementation using existing httpx, tested only with MockTransport. The default transport denies requests, and real HTTP transports cannot satisfy readiness. No credentials are loaded; the only Authorization value is a non-credential mock sentinel. Factory selection and all existing investigation authorization/export gates remain intact. Managed concurrency is now capped at one.

The client creates one session with initial input, polls session and root turn state, reads paginated saved final-answer messages, posts cancellation, and validates public deletion acknowledgments. It checks status/type/IDs/usage, ignores private reasoning, rejects unexpected tools/subagents, and bounds deadlines, retries, response/output bytes, pages and HTTP attempts. Four attempts are reserved for cleanup; POST creation/cancellation never auto-retry. Safe usage/source/request counters merge into existing metadata. Physical provider cleanup and billing termination are not inferred from acknowledgments.

See current contract (local-only reference; not included in this release) and [managed plan section 12](MANAGED_AGENT_EXECUTION_PLAN.md#12-phase-59--disabled-http-transport-mocked-contract-verification). Older no-HTTP statements describe Phase 5.8. Live permission equivalence, authentication, model entitlement, data transfer, spending controls and actual provider behavior remain unverified. No local sandbox policy changed.

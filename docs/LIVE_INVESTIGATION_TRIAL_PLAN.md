> Superseded execution choice: the owner selected fully local Ollama (Option B). This managed plan is historical; managed execution remains disabled and no paid/hosted trial is authorized. See [local AI investigation](LOCAL_AI_INVESTIGATION.md).

# Phase 5.10 — controlled synthetic investigation trial plan

Reviewed 2026-11-15. **Readiness review complete; classification C — blocked for execution.** No provider session, model investigation, evidence upload or paid request was made. No credentials were read or configured. Managed execution remains disabled. This document proposes a future trial; it does not authorize or schedule it.

## 1. Scenario and scope

Investigate one synthetic payment-service fee regression: an amount of 10,000 cents with a rounded two-percent fee should total 10,200 cents; an authored faulty subtraction returns 9,800. The synthetic `CalculationRegression` message is `Payment total violated fee invariant`. The stack trace points to line 6 of an authored nine-line invariant fixture. These values were derived from the source arithmetic; neither the payment fixture nor an investigation agent was executed in this phase.

The intended outcome is an evidence-cited hypothesis and plain-language remediation recommendation, without patches, repository edits, tool execution, delegation or external research. This is a transport/report-validation exercise, not an independent diagnosis benchmark: the synthetic historical reference already describes a similar root cause.

## 2. Exact proposed transfer

The authoritative inventory is transfer-manifest.json (local-only reference; not included in this release). Its status is **PROPOSED ONLY; NOT APPROVED FOR TRANSFER**. Only outbound-evidence.json (local-only reference; not included in this release) is proposed as an input file:

| Property | Proposed value |
| --- | --- |
| UTF-8 size | 3,684 bytes |
| SHA-256 of exact file bytes | `ce6e07c0ff308ea9a61c04f73d4f697e38c23aca74b3d426d9095d32f0830143` |
| Hosted destination | `/workspace/inputs/evidence.json` |
| Submission | One inline base64 file in `environment.files[0].data`; no Files API upload |
| Export schema | `opsguard.synthetic-export.v1` |
| Proposed approval digest | `562998e3bc6c16a0c0a0f241c17b95b32eaba722f39c571d11f1e27639c06751` |

The approval digest covers the raw incident/evidence/limitations bundle excluding its transient investigation ID. It differs from the exact outbound-file hash. It was supplied to an in-memory builder for mechanical validation only; **no approval was installed in application configuration**. User review of this plan does not itself approve the data for transfer.

Export top-level fields are exactly `schema_version`, `synthetic_approval_sha256`, `investigation_id`, `incident_id`, `service_name`, `evidence`, `limitations`, `read_only`. The synthetic incident/investigation UUIDs and all limitations are visible in the file. `read_only` is an application declaration, not a provider sandbox permission.

| Evidence | Exact content scope | Export fields in addition to id/kind/content/export_sha256 |
| --- | --- | --- |
| E001 log | Authored synthetic incident description and stack trace; 578 content bytes | None |
| E002 source | `services/fixtures/faulty-commit.js`, line 1, authored miniature subtraction expression; 66 content bytes | path, start_line, end_line, sha256 |
| E003 source | `services/payment-service/trial-invariant.js`, lines 1–9, authored miniature invariant; 300 content bytes | path, start_line, end_line, sha256 |
| E004 Git | Observed status of an isolated, disposable, unborn Git repository; 199 content bytes | operation=`status` |
| E005 historical | Only synthetic reference `SYN-PAY-004`; 630 content bytes | historical_id, similarity_score, source_ref |

E001's JSON content fields are exactly `synthetic`, `service_name`, `error_type`, `error_message`, `endpoint`, `http_status`, `stack_trace`, `amount_cents`, `expected_total_cents`, `fixture_total_cents`, `evidence_origin`. The endpoint is an invented relative path, not a callable URL. E005's JSON content fields are exactly `id`, `title`, `service_name`, `symptoms`, `error_type`, `error_message`, `root_cause`, `resolution`, `source_ref`, `synthetic`. Its source reference names the synthetic dataset, not permission to upload that dataset.

E005's cosine score, `0.6273181521814969`, was measured locally using cached CPU `all-MiniLM-L6-v2`, revision `c9745ed1d9f207416be6d2e6f8de32d1f16199bf`, dimension 384. Query: `Payment total violated fee invariant`; service filter payment-service, top_k=3, minimum .25. Only the selected projection transfers. The query used a disposable copy of Qdrant; hashes of the original index were unchanged. Socket connections were denied and model loading was local-only with token lookup disabled. No remote embedding request occurred.

An earlier pytest Git fixture expired during preparation. To honor the prohibition on commits, a fresh disposable repository was initialized without add/commit/push. Scoped status showed the authored untracked fixture and HEAD was absent. **No commit SHA, diff or author is supplied; suspected_commits must be empty.** If commit attribution becomes mandatory, separately approved fixture preparation and a new manifest are required.

The request preview (local-only reference; not included in this release) is an unsent 8,176-byte JSON body, SHA-256 `24ee968eb9910fba1945437630758666c8ddf85f87899ec6cd3721ded5b3f471`. It contains the inline file, schema, instructions, initial input and configuration described below. These request fields also leave the application in any future trial and need approval. It contains no authentication header. Base64 is transport encoding, not encryption.

Local-only artifacts: raw bundle, request preview, manifest, preparation results, fixture files and this plan. No original repository, .git directory, whole source file from a private repository, database, Qdrant index, model weights, full history dataset, environment file, SSH credential, provider key or expected-answer rubric is proposed for upload. The fixture paths are logical source identifiers; no original project mount is requested.

## 3. Provider requirements and data policy

The candidate is the beta **OpenAI Agents API with an OpenAI-hosted environment**, not the Agents SDK alone or a local Codex sandbox. Existing direct REST transport uses the documented session/turn/item/event/delete routes. An application API key needs `api.agents.read`, `api.agents.write`, `api.responses.write`, Bearer authentication and `OpenAI-Beta: agents=v1`. Keep the application key in the trusted backend, outside the agent environment. No vault, Files API, MCP, private-network or self-hosted executor key is needed for the proposed subset. [Official quickstart](https://developers.openai.com/api/docs/guides/agents-api/quickstart).

Candidate model `gpt-6-astra` appears in the quickstart and has a documented model ID. Its availability to this particular organization/project, applicable rate limits, billing access and model permissions are **unverified**. A ChatGPT subscription or working local Codex executable is not evidence of this API entitlement. Do not substitute another model silently. [Model reference](https://developers.openai.com/api/docs/models/gpt-6-astra).

Proposed environment: `type=openai_hosted`, `container_size=small` (1 vCPU/1 GB), one workspace, explicit `network.access=disabled`. Outbound access otherwise defaults enabled. No packages, setup commands, env variables, templates, mounts, connectors or artifact publication are requested. Hosted expiry is not an application deadline; explicit deletion is needed. [Hosted environment](https://developers.openai.com/api/docs/guides/agents-api/environments/openai-hosted).

Agents currently supports US data residency only and does not support Zero Data Retention. [Agents FAQ](https://help.openai.com/en/articles/20001551-agents-api-beta-faq). API data is not used for training unless opted in; the Agents data table specifies application state until deletion and default abuse logs for 30 days, with policy exceptions. Deletion is not proof of immediate physical erasure or removal of every provider log. Approval must cover this handling even for synthetic material. [Data controls](https://developers.openai.com/api/docs/guides/your-data).

## 4. Security review and unresolved gates

| Requirement | Current evidence and remaining condition |
| --- | --- |
| No original Mac filesystem access | Proposed data-only hosted request has no host mount, bridge, tunnel, local executor, MCP or repository connection. No host access is granted. Actual provider isolation has not been measured. |
| No secrets/private repositories | Exact authored payload reviewed and accepted by the existing sanitizer/path/size/digest checks. Only the manifest's file may transfer. Pattern scanning is not a universal secret detector. |
| Disposable workspace | Documented hosted per-session workspace; no real session created, so lifecycle not verified. |
| Restricted network | Explicit disabled outbound policy in the preview; not remotely tested. This does not block the trusted backend's control-plane HTTPS or imply no provider infrastructure communication. |
| No modification of original repository | Source excerpts are data inside JSON and no original repository is connected. Hosted workspace write permission is a separate unresolved question. |
| Read-only/child execution permissions | No verified equivalence to the local strict policy. Instructions, tools=[] and rejection of returned tool items are not OS controls. Provider automatic review uses a workspace-write baseline; it is not proof of strict read-only enforcement. |
| Bounded execution | Application deadlines and finite requests exist; provider execution can outlive a client timeout or cancellation acknowledgment. No verified remote hard-stop guarantee. |
| Validated report | Local schema/evidence validation exists. Provider acceptance and genuine report fidelity remain untested. Unknown sources, paths, commits, history, tools or malformed output must fail closed. |
| Cancellation/cleanup | Mocked event/delete interfaces exist. Terminal cancellation, actual deletion, residual artifacts and billing cessation remain unverified. |

The provider warns that generated code can access what its environment exposes; automatic review does not replace isolation/network/credential controls. [Sandbox security](https://developers.openai.com/api/docs/guides/agents-api/environments/security).

**Blocking implementation findings:**

1. The current factory uses a denying transport; only an explicitly injected mock can be eligible. There is no reviewed live credential path. Enabling configuration flags alone cannot run this trial.
2. Evidence exists only as a workspace file, while instructions prohibit tools and result parsing rejects command execution. The review has not established tool-free model access to those file bytes. A supported, reviewed input design must resolve this before execution; do not simply allow shell commands or weaken containment.
3. Provider-enforced strict read-only and child-execution restrictions have not been established. Output filtering can detect an unexpected tool after execution; it cannot prevent the action. If the provider cannot represent the required permissions, retain blocked status.
4. Live provenance/recovery must be implemented deliberately. The eligible current path marks reports TEST DOUBLE; flipping a gate without updating that path would mislabel output. Preserve test-double labeling in tests and use genuine provider identity only after actual execution.
5. Cancellation/ambiguous creation reconciliation and cleanup require a reviewed operational owner. A failed create may have provisioned work without returning its ID. Never blindly resubmit.

No fixes or activation were applied during this planning phase.

## 5. Cost review

Illustrative Standard short-context Astra rates: $10/M input, $50/M output; cached input $1/M; 30-minute/12-hour cache writes $12.50/$25 per million. A 1 GB container is $0.03 per 20-minute block; eligible sessions use per-minute billing with a five-minute minimum. Eligibility is not assumed. [Official pricing](https://developers.openai.com/api/docs/pricing).

| Assumed aggregate billed tokens across the investigation | Inference + one container block |
| --- | --- |
| 10,000 input + 4,000 output | $0.10 + $0.20 + $0.03 = **$0.33** |
| 30,000 input + 12,000 output | $0.30 + $0.60 + $0.03 = **$0.93** |
| 50,000 input + 10,000 output | $0.50 + $0.50 + $0.03 = **$1.03** |

These are assumptions, not tokenizer measurements or caps. Include reasoning output, repeated harness inference, cache operations, additional/idle container blocks, and optional tools if later enabled. No optional tools are proposed. Tax/FX may apply; no separate transfer/storage charge was established for this exact inline-only design. Do not assume unrelated free storage allowances apply. The preview does not pin a service tier: confirm the billed tier/rates before authorization. No free live trial entitlement is assumed.

Proposed application limits, **not applied**: one investigation/session, one concurrent session, 16 KiB evidence, 32 KiB accepted report, 64 KiB HTTP response, 60-second analysis deadline within the existing 90-second worker deadline; 2-second request and cleanup deadlines; 32 HTTP attempts with four reserved for cleanup; one GET/DELETE retry, no create/cancel POST retries, four result pages, one-second polling. Polling may exhaust the request budget before the duration limit. HTTP attempts do not bound internal model calls; output-byte rejection happens after generation. Counters are per client/session, not a durable global billing ledger.

Provider-side controls are separate: an account/project owner should verify model/rate restrictions, billing visibility and enforced spend settings. Alerts alone do not stop requests; documented hard-limit enforcement can lag and overshoot. [Project limits](https://help.openai.com/en/articles/9186755-managing-projects-in-the-api-platform). Neither these settings nor the application limits guarantee an exact dollar cap. A future owner may approve a $2 exposure target with overshoot risk explicitly acknowledged; **no such approval exists now**. If a guaranteed $2 maximum is required, do not execute.

## 6. Checklist — all live gates remain open

- [ ] Account owner confirms Agents beta/project entitlement, billing and model access without disclosing credentials in chat or artifacts.
- [ ] Reviewed live transport, secure backend-only credential delivery and genuine provenance implemented and tested separately; mock behavior preserved.
- [ ] Credential owner approves only the three required scopes; no key enters agent files, environment or logs.
- [ ] Model and billing tier selected explicitly; current pricing and all potential charges reviewed immediately before the trial.
- [ ] Data owner approves the exact file hash, every field, request instructions/schema, US processing and retention. Any payload change requires a new manifest and approval.
- [ ] Spending owner authorizes exactly one investigation and accepts cancellation/billing overshoot risk; provider limits and billing observer verified.
- [ ] Tool-free evidence access resolved using a supported interface without broadening permissions.
- [ ] Security reviewer establishes strict provider permissions, original-host separation, disposable workspace and outbound-denial behavior. Any necessary security probe/session needs its own explicit authorization; it is not part of this review.
- [ ] Deadlines, concurrency, byte/request limits and no-auto-resubmission behavior reviewed; no overlapping workloads or local models started.
- [ ] Named operator can cancel and delete; distinguish acknowledgment, terminal execution and physical cleanup. Reconciliation path and unresolved-create response agreed.
- [ ] Expected schema/evidence checks below approved; Git commit attribution explicitly out of scope for this unborn fixture.
- [ ] User gives a new, explicit execution authorization after the blockers close. Approval of this document alone is insufficient.

## 7. Conditional execution procedure — not executed

1. Close the gates above in separately authorized work. Re-check official contract, pricing, account access and manifest hashes. Keep local Codex restrictions unchanged; retain disabled mode until all approvals exist.
2. Admit exactly one synthetic job through the existing orchestrator. Persist backend/provenance/export digest before submission. Only approved fields enter the sanitized bundle; do not collect arbitrary current repository contents.
3. With new explicit authorization, create one hosted session with one initial input. This operation starts inference and may bill immediately. Record its real identifier durably before polling. Do not retry an ambiguous creation or create a replacement session.
4. Poll bounded session/root-turn state; idle alone is not completion. Stop on failure, cancellation, unsupported actions/tools, schema violations or budget exhaustion. No follow-up inference turns or approval grants.
5. Retrieve one final structured answer, validate locally against the actual approved evidence, record available usage with its session/turn source without double counting, then store through existing SQLite/report APIs for the Next.js view. Usage may be incomplete and is not an invoice. Do not store private reasoning.
6. On timeout/cancel/error, send the documented cancel event and pursue bounded deletion/reconciliation. On success, delete the session too. Acknowledged cancel is not terminal cancellation; public deletion is not physical-erasure proof. Persist unknown/pending cleanup, block new jobs, and assign manual follow-up if unresolved. Do not download artifacts or access private local files.
7. Have the owner reconcile actual usage/billing and review the report and cleanup outcome. A successful investigation does not certify every provider security property or authorize another run.

Session cancellation uses `agent.session.input.cancel`; closing a stream does not cancel execution. [Session lifecycle](https://developers.openai.com/api/docs/guides/agents-api/sessions), [deletion contract](https://developers.openai.com/api/reference/resources/beta/subresources/agents/subresources/sessions/methods/delete).

## 8. Expected output and acceptance

Use existing `AgentAnalysis`: error_summary, suspected_root_cause, verified_facts, explanation, affected_files, suspected_commits, historical_references, recommended_remediation and limitations. Cite E002 line 1 for the arithmetic hypothesis, E003 for the invariant, E001 as authored incident context, E004 for the lack of revision attribution and E005 as similar synthetic history. Do not claim a reproduced causal failure. Confidence must remain within the existing validator's bounds without causal reproduction. Remediation is descriptive text only, with no generated/applied hotfix or patch.

Pass requires a genuine provider response with accurate live provenance, one validated final answer, only approved source IDs/paths/ranges/history, empty suspected_commits, explicit synthetic/unexecuted limitations, bounded session behavior, accounted usage when available and a documented cleanup outcome. No secret, original-host access, unapproved transfer, tool execution or repository change is acceptable. Missing evidence access, unsupported permissions, invented facts/commits, malformed output, unknown create state, unresolved cleanup or unexpected charges fail the trial; never replace them with test-double success.

## 9. Verification performed in this phase

Preparation results (local-only reference; not included in this release) record **26 passing local artifact checks**, including in-memory export validation, the local selected `CreateSession` schema validation, exact inline bytes, source ranges/hashes and document links. Preparation also verified actual disposable Git status, the offline historical score and unchanged original Qdrant hashes. These are artifact checks, **not provider contract acceptance or sandbox tests**. No agent or payment failure was executed; no account/credential inspection occurred. Application code/configuration/dependencies and SQLite data were untouched. No full regression suite was rerun for this documentation/artifact-only phase; the 166 backend tests and 54 mocked HTTP tests in Phase 5.9 results (local-only reference; not included in this release) remain historical results.

Planning deliverables are complete. **C — blocked for one live investigation** until transport/provenance, evidence-access and permission/security gates close and account, data and spending approvals are supplied. No session has been created to investigate these unknowns. Phase 6 has not begun; no commit, push or deployment occurred.

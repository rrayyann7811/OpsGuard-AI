# Investigation evaluation — real AI benchmarking pending

No live Codex reasoning, accuracy measurement, completion-time benchmark or confidence calibration was performed. No paid API resources were consumed. The current native containment probe fails with SIGABRT; the adapter blocks execution. `evaluation/agent_results.json` (local-only reference; not included in this release) explicitly records PENDING_LIVE_CODEX and null metrics, rather than fabricated zeros or success rates.

## Cases and reproducible evidence

`evaluation/investigation_cases.json` (local-only reference; not included in this release) contains ten clearly synthetic controlled cases: missing amount, null access, simulated DB refusal, request timeout, invalid configuration, calculation regression, slow downstream, repeatable 500, faulty Git fixture and authentication simulation. Each includes expected source path, known root cause, relevant error type/message, expected terms and a synthetic label. The nine shared controlled branches live in the existing real services/shared/app.js; the faulty fixture points to services/fixtures/faulty-commit.js.

The fixture builder creates actual commits only in a fresh disposable repository, including known correct and faulty fee calculations. Source/Git evidence is read from actual files/commands, never invented. Curated evaluation error text is labeled synthetic input, not represented as a newly observed live log. The separate application integration test does trigger an actual Node failure and validates its ingestion/evidence path, with only the agent explicitly doubled.

## Variants

The opt-in runner compares the same cases with:

- logs_only: incident/error evidence only; source attribution may be insufficient.
- logs_git: logs plus source inspection and Git evidence (the name includes source context explicitly).
- logs_git_rag: the same logs/source/Git plus actual Phase 4 retrieved references/scores.

The production API always performs the full workflow; these ablations are evaluation tooling, not a way to bypass source permissions. Historical matches remain supporting context, not ground truth. A missing index/context is recorded as a limitation.

## Metrics and limits

`python -m app.agent_evaluation` scores captured actual live reports only. Test-double records are rejected as AI benchmark input. Metrics are grouped by variant:

- Root-cause accuracy requires independent `reviewed_root_cause_correct` boolean labels. Until reviewed reports exist, this metric is null.
- Keyword coverage is a separately named diagnostic proxy; it is not semantic root-cause accuracy.
- Affected-file accuracy checks the expected file against validated structured locations.
- Evidence attribution correctness reruns schema/provenance/range/hash validation. It does not measure whether the evidence logically entails the prose.
- Completion time is measured elapsed time for completed investigations; no invented timing is used.
- Failure rate is non-completed attempts / all recorded attempts per variant.
- Incorrect-confidence rate is the fraction of independently reviewed reports that are incorrect but received MEDIUM/HIGH evidence-coverage classification. This is not a calibrated probability.

The current confidence method is structural evidence coverage (defined in AGENT_ARCHITECTURE.md), never a model percentage. HIGH is not assigned in read-only Phase 5. Independent human review is still needed for semantic validity, source relevance and correctness of hypotheses. Ten controlled synthetic cases, short files and fixture commits do not establish real-world generalization.

## Commands

Create the explicit pending report without invoking an agent:

```sh
cd backend
.venv/bin/python -m app.agent_evaluation
```

After verified containment and separate paid-use authorization, the runner can capture actual reports:

```sh
# Potentially billable. Currently BLOCKED on this host; no fallback agent.
.venv/bin/python -m app.agent_benchmark --authorize-paid-execution --case INV-EVAL-06 --variants logs_git_rag --output ../evaluation/agent-live-run-01.json
# All ten cases × three variants would authorize up to 30 separate agent turns:
# .venv/bin/python -m app.agent_benchmark --authorize-paid-execution --variants logs_only logs_git logs_git_rag --output ../evaluation/agent-live-comparison-01.json
```

The runner refuses an existing output path, uses a disposable source/Git fixture, reads the existing historical index, applies normal report validation, records actual durations/failures and never substitutes a fake agent. Stop the API first if using the same embedded Qdrant path. It deliberately requires dedicated credentials/model and the same containment gate. After independent reviewed labels are added, score the recorded file:

```sh
.venv/bin/python -m app.agent_evaluation --reports ../evaluation/agent-live-run-01.json --output ../evaluation/agent-reviewed-metrics-01.json
```

No live reports or benchmark numbers are claimed in this implementation. The deterministic application tests and their runtime are software verification, not model-quality results. Repair and verify the containment runtime before running paid tests; do not bypass host isolation to obtain a benchmark.


## Final audit checkpoint

All deterministic acceptance checks passed: 74 backend tests, 26 frontend tests, 25 microservice tests, two no-credentials adapter unit tests, and the separately executed process-backed workflows. Three frontend integrations are skipped only in the routine unit suite and passed through their runners. The Phase 5 end-to-end report was explicitly test-double-generated; real source/Git/RAG/incident evidence and report persistence/display were verified, but this provides no root-cause accuracy result for Codex.

The separately changed non-AI containment diagnostic still failed with SIGABRT before /bin/cat output. The normal host probe remains skipped in routine tests; live execution is blocked, not silently replaced. There are still no actual AI report records or independently reviewed labels, so agent_results.json retains null accuracy/time/failure/confidence metrics and live_execution_performed=false. No paid request was made.

The existing Phase 4 real-vector evaluation was checked for consistency using a separate temporary output: all 24 query rankings and all quality metrics matched the saved baseline across all three methods. Those retrieval results must not be confused with investigation-agent evaluation. The baseline and persistent knowledge data were preserved.

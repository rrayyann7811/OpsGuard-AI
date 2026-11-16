# Read-only Codex investigation adapter

Official @openai/codex-sdk 0.169.0, pinned locally. Application-controlled collectors supply bounded, redacted incident/source/Git/RAG evidence. The SDK receives a disposable evidence workspace, strict output schema and no original repository authorization. No generated patches or source modifications.

**Implemented with live verification pending.** The current macOS containment self-test fails with SIGABRT; live execution is blocked. No paid agent call ran. Missing runtime/credentials never triggers a fake fallback.

`npm ci` installs; `npm test` runs no-credentials unit tests. `OPSGUARD_SANDBOX_TEST=1 npm test` is a separate non-AI host probe (failed on this host, accurately reported). Python's backend adapter controls authorization, bounds and persistent orchestration. Read [architecture](../docs/AGENT_ARCHITECTURE.md), [workflow/setup](../docs/INVESTIGATION_WORKFLOW.md), and [evaluation](../docs/AGENT_EVALUATION.md).

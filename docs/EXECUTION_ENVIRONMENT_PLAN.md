# Phase 5.5 — Execution environment readiness

Assessment date: 2026-11-15. **Planning complete; execution environment not verified.** Phase 5 remains **Implemented — live Codex verification pending.** No paid requests, provisioning, installations, policy relaxation, repeated containment probes, source changes, or Phase 6 work were performed in this checkpoint.

## 1. Current failure and diagnostic evidence

The application intentionally refuses live execution unless its non-AI containment self-test succeeds. The current macOS ARM64 launcher in `agent/sandbox-codex.mjs` wraps the pinned native CLI in a custom deny-default Seatbelt policy. Its intended scope is sanitized evidence plus public runtime files, disposable home/tmp writes, and execution of only the native CLI. Original repositories are not granted to the agent. **These intentions have not been established as effective OS enforcement.**

Reviewed: `agent/adapter.mjs`, `agent/sandbox.mjs`, `agent/sandbox-codex.mjs`, `agent/containment.mjs`, `backend/app/codex_adapter.py`, source/Git restrictions in `backend/app/agent_evidence.py`, agent settings, README, progress, architecture, workflow, evaluation documentation, and `evaluation/phase5_audit.json`.

| Evidence | Interpretation and limit |
| --- | --- |
| Prior allowed `/bin/cat` sentinel read aborted with SIGABRT, no output | Failure precedes SDK/model execution; not exclusively an SDK/model problem. |
| Prior changed policy added narrow executable mapping; the allowed read still aborted | A missing executable-mapping allowance alone did not explain or repair the failure. Candidate policy was not adopted. |
| Prior approved strict signature checks passed for cat, sh, sandbox-exec and pinned CLI | Earlier restricted-context signature errors do not establish binary corruption. |
| This checkpoint: native CLI `sandbox macos --help`, temporary HOME/CODEX_HOME/TMPDIR, no credentials, returned 71 and `sandbox-exec: sandbox_apply: Operation not permitted` | Additional execution/sandbox restriction evidence. This was help-only, not a containment test or model call. Does not prove which enclosing policy rejected initialization or explain the earlier SIGABRT. No unchanged retry followed. |
| `sw_vers`: macOS 27.2.1, build 26B131 | Reported platform, not an independently certified compatibility result. |
| `command -v docker` found no executable | Docker CLI unavailable in this session; no daemon/VM/container validation claimed. |
| `sysctl -n hw.memsize` denied by the execution context | RAM was not measured; the user's 8 GB Apple Silicon specification is the planning target. No private diagnostics were accessed. |

**Root cause is not conclusively established.** Leading explanations are enclosing execution restrictions/sandbox initialization denial, or an unmet requirement in the custom restricted runtime policy. Nested sandbox behavior and OS/runtime compatibility remain possible. Generic command failure prevents attributing this solely to the SDK. No evidence establishes a provider authentication/model error: the workflow has not reached that stage. No repeated unchanged probe, private crash-log inspection, security disablement, or unrestricted execution was used.

The installed official TypeScript SDK is pinned to `@openai/codex-sdk` 0.169.0. Its `Codex`, `startThread`, `run`, structured output and AbortSignal integration are implemented. It wraps a local CLI, not an automatic remote execution service ([SDK source](https://github.com/openai/codex/blob/main/sdk/typescript/README.md), [SDK guide](https://learn.chatgpt.com/docs/codex-sdk)). The application launcher currently resolves a **Darwin ARM64 binary explicitly** and rejects other platforms. A Linux image cannot run this adapter unchanged. Do not install a different SDK or rewrite the worker merely to mask the failure.

## 2. Evaluated options

### A. Supported local macOS sandbox

Dependencies: existing Node.js/SDK/native ARM64 CLI, macOS sandbox facilities and a verified restricted runtime. No Linux VM or model-weight download is needed. Official Codex uses Seatbelt on macOS and provides a non-AI `codex sandbox macos` diagnostic; its restricted-read profiles incorporate curated platform access ([security documentation](https://learn.chatgpt.com/docs/agent-approvals-security)). A future supported-profile comparison must use a fresh synthetic workspace and no credentials; it must not weaken the application's gate.

Advantages: smallest memory/disk overhead, current platform match, no hosting charge. Setup is low complexity **only when OS containment works**; this host currently blocks it. Read-only alone is not a guarantee against reading secrets: explicit read boundaries, isolated configuration and denied child execution remain requirements. The custom outer wrapper is additional project policy, not proof that OpenAI's standard macOS sandbox is broken. No global OS setting, signing override, unrestricted terminal grant or sandbox exemption is recommended. Suitability for 8 GB: best resource fit, currently unavailable pending a verified fix or supported explanation.

### B. Dedicated isolated Linux/ARM64 container — recommended target, conditional

Dependencies: an approved Apple Silicon Docker Desktop installation, supported macOS release, native ARM64 Linux image, Node.js, pinned Linux-compatible Codex runtime, and a small platform-specific containment adapter. Keep Python, SQLite, Qdrant and embedding weights on the host. Transfer only bounded sanitized evidence; never mount the original repository or personal home.

The VM separates the Linux kernel from macOS; non-root containers add namespace/resource boundaries. Containers sharing that VM are not independent physical machines, and the Docker daemon remains trusted. Official Codex uses Linux bwrap/seccomp; container restrictions can prevent those mechanisms from initializing. OpenAI documents both retaining the inner sandbox and an alternative relying solely on container isolation. **The latter is excluded by this project's instructions.** If inner sandboxing cannot pass under the approved restricted container policy, this option is blocked; do not use privileged execution, broad extra capabilities, unconfined seccomp, or sandbox-bypass modes to force it ([official security guidance](https://learn.chatgpt.com/docs/agent-approvals-security)).

Docker supports Apple Silicon and requires at least 4 GB host RAM. That host minimum is not a guarantee that the complete OpsGuard workload fits. Docker VMM requires at least 4 GB allocated to its VM; Docker also documents Apple Virtualization framework as a stable option. Confirm which supported options the selected release exposes before installing; do not assume an installer backend flag selects the same options as Settings ([Mac requirements](https://docs.docker.com/desktop/setup/install/mac-install/), [VMM documentation](https://docs.docker.com/desktop/features/vmm/)).

Setup complexity: medium to high; new launcher work and non-AI containment tests are required, not a backend/frontend rewrite. This is a proposed path, not a working container configuration or a claim Docker fixes the Mac probe. Resource estimates and approval gates are below.

### C. Supported managed sandbox

Codex Cloud provides managed remote task environments, configurable network policy and repository connections. It avoids loading a Linux VM onto the Mac, but tasks can edit their remote workspace. Do not connect/upload the original project or its home-level Git repository. Any later trial must use a separately approved evidence-only disposable workspace, with no secrets, repository write integration, private network connection, or original repository access. Entitlements, available machine sizes, retention and cost must be confirmed for the user's account ([Cloud environments](https://learn.chatgpt.com/docs/environments/cloud-environments), [Cloud usage](https://help.openai.com/en/articles/20001545-using-codex-cloud)).

The existing TypeScript adapter does not turn into a Cloud job by changing a hostname. No compatible remote job API or equivalent read-only enforcement was verified for this project; separate integration and containment review would be required. A manual Cloud task would not by itself pass the current application's live integration acceptance criteria.

OpenAI also supports **Responses API hosted shell containers** with explicit network policy. This is a different API/runtime, not a drop-in Codex SDK sandbox. It would require a separately reviewed adapter, compatible model and credential/data policy; replacing the current agent is outside this checkpoint ([hosted shell](https://developers.openai.com/api/docs/guides/tools-shell)). Excellent local RAM fit, but greater hosting/data-governance dependence and potentially recurring usage charges. Provider isolation does not make prompt instructions an enforceable read-only policy.

| Criterion | A: macOS | B: dedicated local container | C: managed environment |
| --- | --- | --- | --- |
| Existing adapter compatibility | Native target; containment blocked | Linux launcher adaptation needed | Separate remote interface needed |
| Host isolation | Depends on verified OS policy | VM + container + required inner sandbox | Provider boundary; no original host mounts |
| Local resource demand | Lowest | Tight on 8 GB; measure first | Minimal local execution overhead |
| Reproducibility | OS/profile dependent | Pinned image/runtime plus gate | Provider configuration/version dependent |
| Potential costs | Model usage | Model usage; education-eligible Docker | Model/plan, compute and possibly storage |
| Ready for a paid request now | No | No | No |

## 3. Recommendation and resource budget

Recommend **B: a dedicated local Linux/ARM64 container with the Codex inner sandbox retained**, subject to non-AI feasibility verification. This offers a reproducible boundary separate from the failing macOS wrapper, keeps the current SDK and host evidence collectors, and avoids recurring hosted infrastructure. It is a target for the next explicitly approved implementation step, not assurance that default Docker supports the required nesting.

For this 8 GB Mac, first confirm a supported Apple Virtualization framework option with an approximately **2 GB VM budget**. Plan one investigation at a time, approximately **1 GB container memory, one CPU, 64–128 PIDs**, bounded tmpfs/output, and an overall 90-second deadline. These are starting budgets, **not measured usage, certified minima, or promised compatibility**. Node's existing 256 MB heap does not cap native CLI memory. Allow approximately **8–12 GB free disk** for Desktop, one minimal image and working space; actual download/storage sizes must be reviewed before approval. No embedding model download is required for the agent.

macOS, the browser/editor, frontend, Python/PyTorch and local Qdrant still need memory. Use the existing production frontend for a demonstration rather than concurrent dev builds; keep RAG on the host and do not duplicate its model inside the image. Observe Activity Monitor/memory pressure during a no-credentials trial. If the chosen supported runtime needs a 4 GB VM, or inner sandboxing fails with restricted settings, **stop** rather than promise comfortable full-stack execution on 8 GB. A separately approved dedicated Linux lab machine can then be assessed with the same restrictions; do not provision one automatically. No available option is verified today.

## 4. Required security properties

1. Preserve the current fail-closed macOS gate until an independently tested platform adapter is explicitly selected. Never silently fall back to the host, fake reasoning or an unrestricted runtime.
2. Source/Git collection stays application-controlled and read-only: approved service roots only, descriptor/symlink protection, fixed Git arguments and bounded output/time. The project's inherited home-level Git root remains rejected. Use owned synthetic Git fixtures when demonstrating commits.
3. Only normalized, redacted evidence JSON enters an isolated job. No source-root/home mounts, environment files, SSH agents, personal Codex state, MCP servers, plugins, hooks, repository credentials, database files or Qdrant storage enter the runtime.
4. Non-root UID, read-only root filesystem/evidence, bounded writable disposable home/tmp, dropped capabilities, no-new-privileges, default seccomp, resource/PID limits. No privileged container, Docker socket, host network/PID namespace or unrestricted child commands. tmpfs noexec can be defense in depth but cannot alone stop interpreter execution.
5. Retain Codex read-only/approval-never settings and disabled tools. Verify equivalent OS denial of child execution and writes, not just absence of tool calls in a report. If required restrictions are incompatible with the native runtime, report the blocker; do not weaken them.
6. Non-AI filesystem probes run with networking disabled and no credentials. Later provider transport must be separately constrained to reviewed API destinations; Docker bridge networking is not an egress allowlist. Block host/LAN/metadata endpoints and arbitrary outbound access. Keep model network tools disabled. The current Mac profile permits transport outbound generally, so it is not proof of domain-level egress protection.
7. Dedicated server-side credential only after authorization. Do not put it in image layers, build arguments, evidence, command lines, output or browser configuration. Do not inherit personal account state. Runtime credential delivery and log redaction require their own test.
8. Application-owned launcher, bounded stdout/JSON framing and timeout/cancellation of the complete job. No API retry loop, auto-resume after restart, or automatic repeated paid attempts. Persist safe failure metadata without tokens.
9. Continue strict schema, evidence-ID, source/range, real-commit and historical-reference validation outside the container. Real citations do not prove causal conclusions; preserve hypothesis/limitation labels and evidence-coverage confidence categories.
10. Destroy only the newly owned job's disposable runtime after completion. Never delete existing Docker volumes, unrelated containers, operational SQLite/Qdrant records or Git history.

## 5. Installation requirements and costs

Nothing was installed or downloaded in this checkpoint. Docker Desktop, VM/base-image downloads and any required runtime dependencies need explicit approval first. Use official Apple Silicon downloads and review the installed release's supported macOS range. Do not install Rosetta or emulate AMD64 for this ARM64 plan unless a separately justified dependency requires it.

Docker Desktop currently lists education/personal use as free; organizational eligibility must still be checked ([license](https://docs.docker.com/subscription-billing/desktop-license/)). Local execution has no recurring hosting fee but still consumes disk, RAM, electricity and **billable model tokens**. An existing ChatGPT entitlement does not authorize use of this application's dedicated API key or imply free API calls. There is no defensible per-investigation price until the actual supported model and token budget are selected. Estimate input tokens × input rate plus output tokens × output rate, including any applicable cached-token rules, and obtain a per-run spending authorization. Budget alerts are not assumed to be hard spending stops.

For comparison, published hosted-shell container pricing lists 1 GB at **$0.03 per 20-minute session**, with larger sizes and an eligible per-minute/minimum-session qualification; model tokens are additional. This is hosted-shell pricing, **not a quote for Codex Cloud**, a promise of free setup, or a price for the selected local container. Confirm rates/entitlements immediately before any authorized trial ([official pricing](https://developers.openai.com/api/docs/pricing)). No paid infrastructure, account/model availability or actual bill has been tested.

## 6. Step-by-step setup plan — future work, not executed

1. Review this plan and approve only the installation/download scope and non-AI feasibility work. Keep `AGENT_EXECUTION_ENABLED=false`; omit provider credentials. Select supported Desktop version/VMM and verify available disk/RAM without changing OS security settings.
2. Install the official Apple Silicon Docker Desktop release only after approval. Confirm license, virtualization support, `docker version`, `docker info` and actual selected VM backend. Review file sharing; do not share the original project/home with the agent runtime. Set an agreed RAM/CPU/disk ceiling before pulling an image.
3. In a newly owned development directory, prepare a minimal native ARM64 image with pinned Node/SDK/CLI and reproducible dependency lock. Inspect package integrity/platform binaries. No `codex-universal` image, full repository clone or large toolchain is needed for bounded evidence analysis. Record image digest and dependency versions. Image creation is still pending, not a documented existing project command.
4. Implement and review a small Linux-specific launcher behind the existing adapter boundary in a separately authorized change. Keep persistent worker/report/API/frontend contracts unchanged. Do not pretend the Darwin-only native path is portable. The launcher must be selected explicitly and never report ready from image availability alone.
5. With no credentials/network and only owned synthetic fixtures, prove allowed evidence reads; denied outside reads, traversal/symlink escapes and workspace/source writes; denied child shell execution; native CLI startup; bounded memory/PIDs/output; full cancellation/timeout cleanup. Verify Codex's inner sandbox under the restricted container policy. Use the pinned CLI's help to confirm supported diagnostics rather than copying newer documentation flags blindly. Stop after a failure, retain evidence and investigate a materially changed hypothesis before retrying.
6. Verify egress restrictions separately without a model request. Then run all existing deterministic backend/adapter/frontend tests and the Phase 3–5 workflows. Preserve operational SQLite and Qdrant; use disposable integration data and authorized Git fixtures. Record exact pass/fail/skip results, not merely an image build.
7. Present non-AI containment evidence and remaining risks. Only then request separate, explicit approval for **one** real model turn, a named account-supported model, evidence payload scope and spending cap. Establish dedicated credential delivery; never inspect personal credentials or automatically consume credits.
8. Start existing local services, trigger a real controlled payment failure, verify persisted incident and actual RAG references. Submit one authenticated investigation with explicit paid authorization. Readiness must pass immediately before execution; no test-double fallback or automatic retries.
9. Confirm real SDK thread/usage metadata, source/Git/RAG citations, strict report acceptance, SQLite persistence and dashboard display. Review root-cause hypotheses independently; verify original source/Git unchanged. Record measured duration/resources/cost where available, redact identifiers/secrets appropriately and retain useful audit artifacts.
10. Only after all live criteria pass, update Phase 5's verification status. Ten-case/three-variant benchmarking is separate billable work and needs separate approval. Phase 6 and patch generation remain out of scope.

For the macOS diagnostic alternative, a future changed test may compare the **official** CLI sandbox with the custom wrapper in an approved restricted context using only synthetic sentinel files. Obtain supported denial diagnostics where available. Do not rerun today's failed help invocation or unchanged probe, move to unrestricted execution, or relax policy to make it pass. If OS bootstrap is denied before useful diagnostics, supply the sanitized version/platform/error record to OpenAI support or the environment administrator; no private crash dumps or credentials are necessary.

## 7. Live verification acceptance criteria

- Tested runtime/version/image/OS documented; allowed operations succeed and every required denial is observed under the actual launcher. Runtime readiness is false after any failed check.
- Original repository and secrets unavailable to the agent; no host socket, privilege escalation, unauthorized child execution, network destination or filesystem write. Provider transport explicitly distinguished from model tools.
- Timeouts, cancellation, process cleanup, resource bounds, output limits, restart failure handling and duplicate prevention verified. No paid automatic retries or fallback execution.
- One explicitly authorized real Codex SDK run against actual persisted incident evidence completes. Actual historical retrieval, approved source evidence and real fixture Git evidence are retained with provenance.
- Structured report validates, persists and displays; actual execution metadata identifies live Codex, not a double. An independent reviewer checks citations, limitations and unsupported claims. Existing incident state/source/Git history remain unchanged.
- Existing regressions pass and artifacts distinguish fresh results from historical counts. Paid metrics remain pending until actual reviewed runs exist; deterministic reports never count as AI benchmarks.

Until these pass, status is **Implemented — live Codex verification pending**, not fully verified or ready for autonomous remediation.

## 8. Remaining risks and checkpoint outcome

Unresolved macOS failure; untested nested Linux sandbox compatibility; tight 8 GB memory budget; unimplemented Linux launcher; unverified account/model entitlement and egress policy; provider usage after cancellation; native runtime/security updates; synthetic-data evaluation limits; and semantic errors despite valid citations. Containers reduce exposure but do not eliminate kernel/runtime vulnerabilities or credential exfiltration risk. Managed alternatives require separate data transfer/retention and read-only-enforcement review.

This checkpoint reviewed records/configuration and current official sources. It did **not** rerun regression suites, alter application code, prove containment, execute AI reasoning, measure new accuracy numbers, install Docker, or launch managed infrastructure. Previous audit counts (74 backend, 26 frontend, 25 microservice tests; Phase 3/4 integrations and Phase 5 test-double workflow passed) remain historical results, not newly executed checks.


## 9. Phase 5.6A — safe Linux/ARM64 container feasibility

Checkpoint: 2026-11-15. **C. Blocked — required isolation unavailable.** Step 1 found no usable Docker installation. Per the explicit stop condition, no downloads, installation, image design/build, container execution, sentinel probes or paid requests followed. This is an environment prerequisite blocker, not an observed failure of Linux containment.

### Checks performed and measured results

| Check | Actual result | Verification boundary |
| --- | --- | --- |
| Architecture: `uname -m`, `/usr/bin/arch` | arm64 | Apple Silicon execution architecture confirmed. |
| Physical RAM: `/usr/sbin/sysctl -n hw.memsize` | 8,589,934,592 bytes = 8 GiB | Initial sandboxed query was denied; a narrowly approved read-only query succeeded. No security settings changed. |
| Current memory: `/usr/bin/vm_stat` | 16,384-byte pages; free 4,727 (~74 MiB), inactive 93,742 (~1,465 MiB), compressor occupied 158,028 (~2,469 MiB) | Point-in-time snapshot only. Inactive pages are not guaranteed allocatable headroom; free pages are not macOS's total available memory. Compression suggests caution but is not a measured memory-pressure classification or container measurement. |
| Disk: `df -h .` on project volume | About 69 GiB available; 228 GiB volume, 66% capacity reported | Host filesystem measurement, not container/image usage. |
| Docker on PATH | `command -v docker` and `shutil.which('docker')` found none | No CLI available to query a daemon. |
| Standard Docker locations | `/Applications/Docker.app`, its Resources/bin/docker, `/usr/local/bin/docker`, `/opt/homebrew/bin/docker` absent | Bounded public installation-path check, not an exhaustive scan of private directories. |
| Other runtime commands | colima and podman not found on PATH | No alternative runtime installed or attempted. |
| Docker daemon / Linux VM | Not verified | No client available; no sockets or private Docker configuration inspected. |
| Existing configuration | Read `services/compose.yaml`, agent sandbox/containment modules and SDK package manifest | Static review only; no Compose runtime validation possible. |

Existing Compose describes the three simulation services, with loopback port bindings, read-only root filesystems, dropped capabilities, no-new-privileges, 128 MiB memory / 0.5 CPU / 64-PID limits and bounded logs. It does **not** define an investigation container. Its limits are configuration declarations, not measured enforcement. Existing service credentials/configuration must not be reused as an agent environment.

The current agent remains pinned to SDK 0.169.0 with a Darwin ARM64 native path and macOS Seatbelt launcher. It was inspected, not replaced or executed. Historical macOS SIGABRT and sandbox_apply diagnostics were not retried. The current fail-closed behavior and repository allowlists are unchanged.

### Checks blocked by the prerequisite

All proposed Linux container checks are **NOT RUN**: allowed sentinel read; outside-workspace and secret-sentinel denial; unauthorized write rejection; symlink/traversal protection; outbound network denial; timeouts; CPU/memory/PID enforcement; native CLI startup; Codex inner sandbox compatibility. No actual Linux kernel/user-namespace/bwrap/seccomp capabilities were measured. The requirements in sections 2 and 4 remain requirements, not successful test results.

Step 4 Linux/ARM64 runtime verification is deferred by the Step 1 stop condition. A future Linux-specific binary resolver/containment launcher and explicit runtime selection are still required; no claim of tested Linux package/runtime compatibility is made. Do not replace the working application or macOS adapter. Image availability alone must never report agent readiness.

### Resource results versus estimates

Physical memory and project-volume free space above are measured. Container memory, CPU, disk usage and startup time are **unmeasured: no container exists**. The earlier approximately 2 GiB VM, 1 GiB container / one CPU, and 8–12 GB disk budgets remain planning estimates, not demonstrated capacity. The confirmed 8 GiB host and current compressed-memory footprint make full-stack headroom uncertain. Do not assume that disk space or a minimum-memory installation check proves acceptable performance. Measure under the intended frontend/backend/RAG workload after approval; do not force a 4 GiB VM if the resulting workload is unsuitable.

### Required next steps and readiness

1. Obtain explicit approval to download/install an official Apple Silicon Docker Desktop release, with its size, license, supported host version, selected VMM and resource ceiling reviewed first. This checkpoint grants no installation approval. No download or installation occurred.
2. Once installed by an approved action, rerun the read-only CLI/daemon/VM checks and confirm actual resource availability. Docker availability does not establish nested sandbox compatibility.
3. Only then design the dedicated non-root, ARM64, disposable investigation container described in this plan. No original source/home mounts, real credentials, host socket, privileged mode, unrestricted network, or policy bypass. Preserve Codex's inner sandbox. Start non-AI tests with networking disabled and owned synthetic sentinels only.
4. Prove all essential containment and resource properties before handling provider credentials. If any essential requirement fails, stop without loosening policy. Verify an equivalent bounded Linux adapter separately from the existing macOS path.
5. One live Codex investigation is **not ready**. It remains gated on actual containment/runtime/resource/egress verification, regression checks and a separate explicit paid-use authorization.

No application source, source-control history, SQLite records or Qdrant data changed. No regression suite was rerun because this checkpoint changed only documentation. Earlier passing test counts remain historical. No Phase 6 work, paid AI requests, commits, pushes or deployments occurred.


## 10. Phase 5.6B — Docker containment and credential-free Codex verification

Checkpoint: 2026-11-15. **C. Blocked for a live investigation.** Docker now works and the outer-container sentinel/resource checks passed. Codex's Linux sandbox did not initialize. The immediate failure is an incomplete diagnostic image: its standalone Codex executable was copied without the bundled bubblewrap companion. This is not evidence of Docker/kernel incompatibility. Runtime testing stopped at that failure, as requested; no model request was made and no sandbox restriction was relaxed.

### Runtime and isolated test architecture

Verified CLI/Engine 29.9.3, Compose 5.7.0 and Desktop plugin 4.99.0. Daemon: Linux/aarch64, kernel 7.0.14-linuxkit, runc 1.5.2, cgroup v2, built-in seccomp, eight virtual CPUs and 4,106,539,008 bytes (3.825 GiB) guest RAM. Docker initially required narrowly approved host access because the Codex workspace sandbox cannot reach the daemon socket. The socket was used only by the host controller and was never mounted into a container. Initial daemon inventory: zero images and zero containers. Desktop allocation was not changed. Full-stack Compose services were not started or verified here.

Disposable work is in `/path/to/private-runtime`. Download approval was obtained before fetching the 171,743,625-byte Codex archive and approximately 78,395,016 bytes of compressed base layers. Codex archive SHA-512 matches both registry metadata and the existing agent lockfile. Only public runtime artifacts, the existing SDK JavaScript module, and authored synthetic test files enter the build context. No project tree, original source, Git directory, private home, database, production credentials or personal Codex configuration enters the image/runtime.

Pinned official Node 22.16.0 bookworm-slim ARM64 base: `sha256:6b84a3d695387c70b7d5f45224899d5bf5bf96c4345bed678f07822927c850a0`. This older base is a feasibility fixture; security currency and dependency/image review remain required before live use. SDK/native CLI: 0.169.0; native binary target `aarch64-unknown-linux-musl`. Final local image `opsguard-56b:offline`: `sha256:c9c772ae8cd72d2c55d788c82fea7ae629ec88b43e8ad690e6ed34f1baf9d288`, Docker-reported size 759,228,325 bytes. This size is not unique physical disk usage.

Runtime policy: UID/GID 1000:1000; read-only root/evidence; **zero host mounts**; network none; no published ports; all capabilities dropped; no-new-privileges; default seccomp; private container namespaces; 256 MiB RAM and zero container swap; 0.5 CPU; 64 PID ceiling; core dumps disabled; 32 MiB noexec/nosuid/nodev disposable `/tmp`; no automatic restart; bounded local logs (two 1 MiB files). Runtime environment contains only image defaults and disposable HOME/CODEX_HOME/TMPDIR. Docker inspect and `/proc/self/status` confirmed UID 1000, zero effective capabilities, NoNewPrivs=1 and Seccomp=2. Build instructions download no packages and use no RUN commands; registry metadata access during build is separate from the offline job.

### Observed containment and resource checks

| Check | Observed result | Boundary |
| --- | --- | --- |
| Allowed evidence read | Exact synthetic text returned | `/workspace/evidence.txt` |
| Unauthorized read | EACCES | Root-owned synthetic `/denied/sentinel.txt`; no private files used |
| Host-only sentinel absent | ENOENT | Unmounted synthetic sentinel name; inspect also confirms no host mounts |
| Unauthorized root/workspace writes | EROFS | Both `/unauthorized.txt` and evidence overwrite rejected |
| Path traversal | EACCES | `/workspace/../denied/sentinel.txt` |
| Symlink escape read/write | EACCES for both | Owned `/tmp/escape` points to synthetic denied target |
| External network | ENETUNREACH | TCP to documentation-only 192.0.2.1:443; network none/no gateway |
| CPU limit | Effective 50000/100000 quota; 21/21 periods throttled | Busy loop used 1.009 CPU seconds over 2.046 wall seconds, about 49.3% of one core |
| Memory limit | memory.max=268435456, memory.swap.max=0; bounded allocation exited 137 with OOMKilled=true | Dedicated disposable allocation container; not host OOM |
| Execution timeout | One-second timeout killed ten-second sleep with SIGKILL | Harmless subprocess timeout; full SDK cancellation/process-tree semantics remain unverified |
| PID ceiling | pids.max=64 | Configuration confirmed; PID-exhaustion enforcement not stress-tested |
| Native CLI startup | `codex-cli 0.169.0`, exit 0 | Version startup only; not inner-sandbox success |
| SDK compatibility | Existing 0.169.0 module imported successfully on Node/Linux ARM64 | No thread.run/model request or complete adapter execution |

These are outer-container boundary checks. They do not establish a workspace-only read allowlist: public system/runtime files are readable, and tmpfs is intentionally writable. Traversal/symlink tests prove the protected sentinel remains inaccessible, not that arbitrary path syntax is rejected. Shell/child execution is possible in this diagnostic image; the existing plan's stronger child-execution denial is **not implemented or verified**. Container boundaries and file permissions must not be reported as equivalent to the macOS deny-default launcher or a working Codex inner sandbox. Networking none proves offline denial, not provider-only egress.

### Exact Codex blocker and stop

The first `codex sandbox linux --help` invocation that reached the native launcher exited **101** before printing help:

```text
thread 'main' (11) panicked at linux-sandbox/src/launcher.rs:60:13:
bubblewrap is unavailable: no system bwrap was found on PATH and no bundled codex-resources/bwrap binary was found next to the Codex executable
```

Archive inventory, performed without another runtime attempt, confirms `package/vendor/aarch64-unknown-linux-musl/codex-resources/bwrap` exists (529,168 bytes). The image assembly copied only `/bin/codex`, losing its required relative companion. This is a checkpoint packaging error, not a demonstrated unsupported platform. No package installation, policy relaxation, alternate sandbox mode, privileged retry or further runtime test followed this blocker. Native `--version` also warned that helper aliases cannot be created under CODEX_HOME `/tmp`; a supported separate bounded home and helper layout require review. Actual nested bubblewrap/user namespace/seccomp compatibility, allowed commands inside Codex's sandbox and inner denials remain **NOT VERIFIED**. Do not infer their success from CLI version or SDK import.

Earlier setup attempts also encountered Docker local-log compression requiring more than one rotation file, missing traversal permission on synthetic image directories, and a nonexistent CODEX_HOME. Those fixture issues were corrected before the final probe and are retained in separate setup evidence. No prior failed attempt is counted as a successful test.

### Measured resources and limitations

- Initial image build: 12.074 seconds; corrected cached fixture build: 0.714 seconds. A detached sleep container's host CLI start took 0.095 seconds; this is a warm `docker run -d` measurement, not Docker Desktop cold boot. The main probe including two-second CPU load and one-second timeout took 3.231 seconds.
- Idle sleep container: 1.477 MiB / 256 MiB, 0.00% CPU, one PID. Probe process RSS after load: 53,673,984 bytes (~51.2 MiB); early cgroup memory.current: 9,920,512 bytes. These are different accounting measures and observation times, not Codex peak-memory estimates.
- Guest `/proc/meminfo`: total 4,010,292 KiB, available 3,360,872 KiB (~3.205 GiB); total minus available ~634 MiB; free 1,572,580 KiB. Guest swap 1,048,572 KiB, all free. Guest cache is reclaimable; configured VM RAM is not actual host RSS.
- Post-test host `ps` sample: Docker virtualization process RSS 7,888 KiB; Apple VirtualMachine XPC RSS 22,992 KiB; other Docker processes also present, sampled CPU 0.0%. These process RSS readings do not capture all guest-backed physical memory and cannot establish the VM's complete host footprint. Guest aggregate CPU was captured only as cumulative counters, not a utilization interval.
- Host `vm_stat` snapshot showed ~2.57 GiB occupied compressor pages and about 74 MiB free pages. Free pages are not available RAM. The host has 8 GiB physical RAM (previously measured); no reliable full-stack headroom or peak native Codex measurement was obtained. No Ollama/models or service stack was started. Desktop resource settings were not increased.

All newly named test containers were removed; final container inventory is empty. Base/test images and downloaded artifacts remain cached for review; no global prune or unrelated cleanup was performed. Do not run the evidence orchestration as a production launcher: it is a recorded one-shot diagnostic recipe and assumes its owned `/private/tmp` build context.

### Adapter compatibility and remaining gates

Static review confirms `agent/sandbox.mjs` resolves only Darwin ARM64; `sandbox-codex.mjs` uses `/usr/bin/sandbox-exec`; `runtimeStatus()` requires Darwin and containmentSelfTest(). The Python adapter launches the host Node process with existing resource/output bounds. Therefore Linux requires an explicitly selected, independently verified container launcher and correct runtime resource layout. SDK import alone does not make the current adapter portable. Application code and its fail-closed behavior were preserved; no compatibility change was justified after the sandbox stop.

Next checkpoint must first assemble the complete supported pinned Linux runtime, then test the inner sandbox under the same restricted policy without model calls. Any failure must stop further runtime attempts. Remaining live gates: inner sandbox denials; equivalent child-execution/filesystem policy; provider-only egress and host/LAN/metadata denial; dedicated credential delivery/redaction; job-wide deadline/cancellation/cleanup and bounded output; Linux adapter integration/regressions; image security review; intended workload resource measurement; model/account entitlement; separate explicit paid-use authorization. None is waived by Docker availability.

**Readiness: C. Blocked. One live Codex investigation is not ready.** No paid requests, investigation-agent source modifications, Phase 6 work, commits, pushes or deployment occurred. No application regression suite was rerun; earlier test counts remain historical. Reviewable evidence and exact fixture recipes are in `docs/verification/phase5.6b/`; temporary binaries/downloads remain outside the project.


## 11. Phase 5.6C — complete runtime packaging and inner sandbox verification

2026-11-15 — **C. Blocked — required containment unavailable under the preserved Docker profile.** Runtime packaging is corrected and verified. The one harmless Codex sandbox initialization attempt reached bundled bubblewrap but failed to create a namespace. No model requests, paid execution, policy relaxation or further initialization retries followed.

### Evidence review and packaging correction

Reviewed this plan, PROJECT_PROGRESS.md, Phase 5.6B results/Dockerfile/diagnostics, the installed SDK/CLI package metadata, official package launcher code, existing adapter/macOS launchers and cached archive. No AGENTS.md was found within the project. The installed SDK remains 0.169.0, requiring Node >=18; its CLI dependency is 0.169.0 and maps Linux ARM64 to `@openai/codex@0.169.0-linux-arm64`.

Reused `/path/to/private-runtime` (171,743,625 bytes) and the cached official Node 22.16.0 ARM64 base digest `sha256:6b84a3d695387c70b7d5f45224899d5bf5bf96c4345bed678f07822927c850a0`. Archive SHA-512 was recomputed in streaming reads and matched `agent/package-lock.json` exactly. No new version, binary, dependency, image pull or system-wide package installation was needed. Native code was executed only in the Linux container.

The archive's `codex-package.json` specifies layoutVersion 1, target `aarch64-unknown-linux-musl`, entrypoint `bin/codex`, resourcesDir `codex-resources`, pathDir `codex-path`. Preserved **all 43 vendor files** under `/opt/codex` with original file modes and directory structure, including:

| File/group | Verification |
| --- | --- |
| `bin/codex` | 290,069,784 bytes, mode 0755; version 0.169.0 starts without the old home warning |
| `codex-resources/bwrap` | 529,168 bytes, mode 0755; starts and prints `bubblewrap built for Codex` |
| `bin/codex-code-mode-host` | 72,018,272 bytes, mode 0755; packaged, not invoked |
| `codex-path/rg` | 4,506,992 bytes, mode 0755; packaged, not invoked |
| Manifest and voice resource tree | All original metadata/libraries/licenses included; voice/code-mode features not started or claimed tested |

All 43 in-container file SHA-256 hashes, sizes and modes match the integrity-verified archive. This preserves the supported distribution instead of guessing the minimum subset. PATH selects the package's bin/path directories; no host runtime path or credentials are inherited. Evidence inventories contain exact hashes. Final initialization image: `opsguard-56c:offline`, ID `sha256:bf5acc36799ac640ec3ef8c693a0a61c31569a016d434b260b2c6eed7454ed9a`, Docker-reported image size 939,507,818 bytes (not unique disk consumption). Preflight and initialization images differ only in diagnostic command syntax; runtime COPY remained cached and identical.

### Preserved security and kernel observations

Daemon recheck: Engine 29.9.3, Linux/aarch64, eight virtual CPUs, 4,106,539,008 bytes VM RAM and default seccomp/cgroup namespaces. Actual container: UID/GID 1000:1000, read-only root/evidence, zero host binds/mounts, network none/no published ports, all capabilities dropped, no-new-privileges, default seccomp, 256 MiB memory and zero container swap, 0.5 CPU, 64 PID ceiling, core dumps disabled, bounded two-file local logs, no restart. `/tmp` remains 32 MiB noexec/nosuid/nodev tmpfs. Added a separate **16 MiB**, UID-1000-owned, mode-0700, noexec/nosuid/nodev disposable `/home/investigator` tmpfs for HOME/CODEX_HOME; this fixes Codex refusing temporary-dir helper aliases without making root writable or removing noexec. No socket, project/source/Git/private-home mount, production credential or personal config is present. Only approved cached runtime/SDK bytes and synthetic fixture/diagnostic files enter the build context.

Observed Linux kernel 7.0.14-linuxkit; `user.max_user_namespaces=15808`; `kernel.unprivileged_userns_clone=1`; the AppArmor unprivileged-userns restriction sysctl path is absent (ENOENT, not evidence that every LSM restriction is absent). `/proc/self/status`: CapEff=0, NoNewPrivs=1, Seccomp=2. Cgroup confirms memory.max=268435456, memory.swap.max=0, cpu.max=`50000 100000`, pids.max=64. No sysctl, capability, seccomp rule, Docker VM allocation or OS security setting changed.

### One actual sandbox initialization and exact stop

The pinned CLI's successful `codex sandbox --help` shows direct command syntax. Unlike assumptions from older versions, `linux` is not a required subcommand. Used the installed help to select:

```text
codex sandbox -c 'sandbox_mode="read-only"' -- /bin/true
```

No SDK turn, model, provider connection or authentication is involved. stdin is ignored, output bounded at 64 KiB, child deadline eight seconds and controller wait bounded with named-container cleanup in finally. Native Codex selected and launched its bundled bubblewrap. **Exit status 1**, empty stdout, stderr:

```text
bwrap: No permissions to create a new namespace, likely because the kernel does not allow non-privileged user namespaces. On e.g. debian this can be enabled with 'sysctl kernel.unprivileged_userns_clone=1'.
```

Elapsed **76.173 ms**; no timeout, output overflow, OOM or signal. The generic diagnostic suggests a sysctl which is **already enabled**. The verified fact is namespace creation denial under the effective restricted profile. Default Docker seccomp/capability restrictions may be relevant, but no syscall tracing or alternate profile test was performed, so the precise denying layer is **not conclusively attributed**. No assumption that adding SYS_ADMIN or disabling seccomp would safely solve this is made. Those changes and privileged mode were not attempted. No Landlock-only fallback or inner-sandbox disablement was used.

**Stopped at this error with zero further initialization retries.** The JSON diagnostic recorder/container exited 0 because it successfully recorded the child failure; that exit is explicitly not accepted as sandbox success. The native command's status 1 is preserved in `initialize-results.json` and `summary.json`.

### Nested containment and adapter gate

Nested allowed-read, unauthorized-read/write, traversal, symlink, subprocess and timeout checks: **NOT RUN — initialization failed before the harmless command could establish successful sandbox execution**. Outer restrictions were confirmed by inspect/status/cgroup, not treated as inner enforcement. Phase 5.6B's outer sentinel/CPU/OOM/subprocess-timeout results remain historical; they are not relabeled as fresh nested checks. A successful version or bubblewrap version is not sandbox readiness.

The existing adapter still resolves the Darwin ARM64 binary and uses `/usr/bin/sandbox-exec`; runtimeStatus explicitly requires Darwin plus containmentSelfTest. Linux would require explicit runtime resolution/container selection, supported helper-home/resource layout and an independently tested launcher preserving the same evidence/report/authorization contracts. Because the security gate failed, **no Linux launcher or production adapter change was implemented**. Existing macOS production code is preserved.

Added one deterministic test asserting Linux remains unavailable and never reports containment verified, using a temporary platform property override and restoring it in finally. Ran that test plus the existing pure profile-scope and missing-authorization guards: **3 passed, 0 failed**. The native macOS containment test was not selected, and no model call or native retry was made. Full backend/frontend/services suites were not rerun because this checkpoint makes no application implementation change; historical pass counts remain historical.

### Resource measurements

| Measurement | Actual result | Limit |
| --- | --- | --- |
| Warm detached start, corrected preflight | 101.937 ms | Host CLI elapsed; not Desktop cold boot |
| Warm detached start, initialization | 148.694 ms | Includes host Docker CLI/start overhead |
| Native version | 8.020 ms | CLI startup only |
| Bundled bwrap version | 0.805 ms | Does not create a sandbox |
| Sandbox initialization attempt | 76.173 ms | Failed; no successful inner workload |
| Initialization cgroup peak memory | 35,921,920 bytes = 34.258 MiB | Includes diagnostic process and job accounting; not full live-model peak |
| Sampled native process VmHWM | 54,484 KiB (~53.207 MiB) | 5 ms /proc sampling; shared mappings differ from cgroup accounting; can miss short-lived descendants |
| Initialization cgroup current after failure | 12,484,608 bytes (~11.906 MiB) | Point-in-time |
| CPU during initialization | cgroup usage delta 36,718 microseconds over 76.173 ms (~48.2% of one core); one period throttled | Includes recorder overhead; short sample |
| Streaming package preflight peak | 136,794,112 bytes = 130.457 MiB | Includes hashing/cache accounting; below 256 MiB |
| Image build | Initial 15.262 s; cached streaming correction 0.612 s; initialization command correction 0.765 s | Build time, not job startup |

The first preflight recorder mistakenly buffered the 290 MB binary for hashing and was OOM-killed (exit 137) under the unchanged 256 MiB cap **before any Codex command**. Replaced hashing with streaming reads and reran only preflight; the corrected run passed. This is a diagnostic-memory implementation error, not a Codex sandbox failure or a reason to increase limits. Original failed evidence is retained.

No unrelated services, Ollama or local language model was started. The existing 8 GiB host/3.825 GiB VM allocation was not increased. Complete VM host physical footprint, full-stack headroom and live SDK/model resource peaks remain unmeasured. All named Phase 5.6C containers were removed and the filtered final Docker inventory was empty; approved cached images/archive/work artifacts remain for review. No global prune or unrelated cleanup occurred.

### Readiness and next decision

**C. Blocked — required containment unavailable under the current allowed security profile.** Not ready for controlled live-investigation preparation or one paid investigation. Packaging is fixed; nested sandbox namespace creation is the remaining immediate blocker. No safe configuration correction within the preserved controls was identified after that denial. Further work requires a reviewed compatible execution environment/security design; it must not silently loosen Docker controls, disable the inner sandbox or run on the host. The stronger child-execution/read policy, provider-only egress, dedicated credential handling, job-wide cancellation/cleanup/output verification, Linux adapter and workload resource checks remain open even if namespace compatibility is later solved. Separate explicit paid-use authorization remains required.

Evidence: `docs/verification/phase5.6c/` contains the complete runtime inventory/integrity record, exact Dockerfile/diagnostic/preparation recipes, original and corrected preflight results, initialization output/status/timings/resource counters, adapter test record and machine-readable summary. Binary/download/build context stays under `/private/tmp`; no runtime binaries were added to the project. No hotfix generation/application, Phase 6 work, model request, commit, push or deployment.

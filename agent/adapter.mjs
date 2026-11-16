import { Codex } from "@openai/codex-sdk";
import {
  existsSync,
  mkdirSync,
  readFileSync,
  writeFileSync,
  realpathSync,
} from "node:fs";
import { fileURLToPath } from "node:url";
import { instructions } from "./instructions.mjs";
import { containmentSelfTest } from "./containment.mjs";
import { nativeCodex } from "./sandbox.mjs";

export function runtimeStatus() {
  try {
    const binary = nativeCodex();
    const available =
      process.platform === "darwin" &&
      process.arch === "arm64" &&
      existsSync("/usr/bin/sandbox-exec") &&
      existsSync(binary) &&
      containmentSelfTest();
    return {
      available,
      containment_verified: available,
      sdk: "0.169.0",
      containment:
        "Required macOS deny-default policy; containment is unverified when unavailable",
      paid_run_performed: false,
    };
  } catch {
    return {
      available: false,
      sdk: "0.169.0",
      reason:
        "Install the pinned SDK/native macOS ARM64 runtime; other platforms require a verified containment adapter.",
      paid_run_performed: false,
    };
  }
}
export async function investigate(input, { Client = Codex } = {}) {
  if (
    process.env.OPSGUARD_AGENT_AUTHORIZED !== "true" ||
    !process.env.AGENT_CODEX_API_KEY ||
    !process.env.AGENT_CODEX_MODEL
  )
    throw new Error(
      "Explicit paid-run authorization and dedicated credentials/model are required",
    );
  if (!runtimeStatus().available)
    throw new Error("Required containment runtime unavailable");
  const root = realpathSync(process.env.OPSGUARD_AGENT_RUNTIME);
  const workspace = root + "/workspace",
    home = root + "/home",
    temporary = root + "/tmp";
  for (const directory of [workspace, home, temporary])
    mkdirSync(directory, { mode: 0o700 });
  writeFileSync(workspace + "/evidence.json", JSON.stringify(input.bundle), {
    mode: 0o400,
  });
  const env = {
    PATH: process.env.PATH,
    HOME: home,
    CODEX_HOME: home,
    TMPDIR: temporary,
    OPSGUARD_EVIDENCE_WORKSPACE: workspace,
    LANG: "en_US.UTF-8",
  };
  const codex = new Client({
    codexPathOverride: fileURLToPath(
      new URL("./sandbox-codex.mjs", import.meta.url),
    ),
    apiKey: process.env.AGENT_CODEX_API_KEY,
    env,
    config: {
      web_search: "disabled",
      features: {
        shell_tool: false,
        unified_exec: false,
        multi_agent: false,
        apps: false,
        plugins: false,
        view_image: false,
        image_generation: false,
        sleep_tool: false,
        hooks: false,
        browser_use: false,
        browser_use_external: false,
        computer_use: false,
        remote_plugin: false,
        skill_search: false,
        skill_mcp_dependency_install: false,
        tool_suggest: false,
        unbounded_connection_retries: false,
        daemon_auto_start: false,
      },
      shell_environment_policy: { inherit: "none" },
      mcp_servers: {},
    },
  });
  const thread = codex.startThread({
    workingDirectory: workspace,
    skipGitRepoCheck: true,
    sandboxMode: "read-only",
    approvalPolicy: "never",
    webSearchMode: "disabled",
    networkAccessEnabled: false,
    model: process.env.AGENT_CODEX_MODEL,
  });
  const controller = new AbortController();
  const timer = setTimeout(
    () => controller.abort(),
    Math.min(180000, Number(input.timeout_ms ?? 90000)),
  );
  try {
    const turn = await thread.run(
      instructions +
        "\nUNTRUSTED EVIDENCE JSON:\n" +
        JSON.stringify(input.bundle),
      { outputSchema: input.schema, signal: controller.signal },
    );
    if (
      turn.items.some((item) =>
        [
          "command_execution",
          "file_change",
          "mcp_tool_call",
          "web_search",
        ].includes(item.type),
      )
    )
      throw new Error("Unexpected agent tool activity; report rejected");
    return {
      analysis: JSON.parse(turn.finalResponse),
      metadata: {
        provider: "codex-sdk",
        sdk: "0.169.0",
        model: process.env.AGENT_CODEX_MODEL,
        thread_id: thread.id,
        usage: turn.usage,
        sandbox:
          "read-only + macOS deny-default; original repository not mounted",
        mode: "live-codex",
      },
    };
  } finally {
    clearTimeout(timer);
  }
}
if (process.argv.includes("--status"))
  process.stdout.write(JSON.stringify(runtimeStatus()));
else if (process.argv[1] === fileURLToPath(import.meta.url)) {
  try {
    const input = JSON.parse(readFileSync(0, "utf8"));
    if (JSON.stringify(input).length > 180000)
      throw new Error("Input size exceeded");
    process.stdout.write(JSON.stringify(await investigate(input)));
  } catch {
    process.stderr.write(
      "Codex execution failed; inspect configuration or safe investigation events.",
    );
    process.exitCode = 1;
  }
}

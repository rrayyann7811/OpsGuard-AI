#!/usr/bin/env node
import { spawn } from "node:child_process";
import { sandboxProfile, nativeCodex } from "./sandbox.mjs";
const binary = nativeCodex();
const profile = sandboxProfile({
  binary,
  workspace: process.env.OPSGUARD_EVIDENCE_WORKSPACE,
  home: process.env.CODEX_HOME,
  temporary: process.env.TMPDIR,
});
const child = spawn(
  "/usr/bin/sandbox-exec",
  [
    "-p",
    profile,
    binary,
    ...process.argv.slice(2),
    "--ignore-user-config",
    "--ignore-rules",
    "--ephemeral",
    "--strict-config",
  ],
  { stdio: "inherit", env: process.env },
);
child.on("error", () => process.exit(1));
child.on("exit", (code) => process.exit(code ?? 1));

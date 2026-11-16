import {
  mkdtempSync,
  mkdirSync,
  writeFileSync,
  rmSync,
  readFileSync,
} from "node:fs";
import { tmpdir } from "node:os";
import { spawnSync } from "node:child_process";
import { sandboxProfile, nativeCodex } from "./sandbox.mjs";

export function containmentSelfTest() {
  if (process.platform !== "darwin" || process.arch !== "arm64") return false;
  const root = mkdtempSync(tmpdir() + "/opsguard-containment-");
  const workspace = root + "/workspace",
    home = root + "/home",
    temporary = root + "/tmp";
  for (const path of [workspace, home, temporary]) mkdirSync(path);
  writeFileSync(workspace + "/evidence.txt", "allowed evidence");
  writeFileSync(root + "/outside.txt", "outside sentinel");
  const run = (binary, args) =>
    spawnSync(
      "/usr/bin/sandbox-exec",
      [
        "-p",
        sandboxProfile({ binary, workspace, home, temporary }),
        binary,
        ...args,
      ],
      {
        encoding: "utf8",
        timeout: 4000,
        env: { HOME: home, PATH: "/usr/bin:/bin" },
      },
    );
  try {
    const allowed = run("/bin/cat", [workspace + "/evidence.txt"]);
    const outside = run("/bin/cat", [root + "/outside.txt"]);
    const write = run("/bin/sh", [
      "-c",
      'echo modified > "$1"',
      "probe",
      workspace + "/evidence.txt",
    ]);
    const execute = run("/bin/sh", [
      "-c",
      '/bin/cat "$1"',
      "probe",
      workspace + "/evidence.txt",
    ]);
    const native = run(nativeCodex(), ["--version"]);
    return (
      allowed.status === 0 &&
      allowed.stdout === "allowed evidence" &&
      outside.status !== 0 &&
      write.status !== 0 &&
      execute.status !== 0 &&
      readFileSync(workspace + "/evidence.txt", "utf8") ===
        "allowed evidence" &&
      native.status === 0 &&
      native.stdout.includes("0.169.0")
    );
  } catch {
    return false;
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
}

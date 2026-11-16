import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, mkdirSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { sandboxProfile } from "../sandbox.mjs";
import { containmentSelfTest } from "../containment.mjs";
import { investigate, runtimeStatus } from "../adapter.mjs";

test("Linux remains unavailable until its containment adapter is verified", () => {
  const platform = Object.getOwnPropertyDescriptor(process, "platform");
  try {
    Object.defineProperty(process, "platform", { value: "linux" });
    const status = runtimeStatus();
    assert.equal(status.available, false);
    assert.equal(status.paid_run_performed, false);
    assert.notEqual(status.containment_verified, true);
  } finally {
    Object.defineProperty(process, "platform", platform);
  }
});

test("deny-default profile declares scoped reads/writes and omits the original repository", () => {
  const root = mkdtempSync(tmpdir() + "/opsguard-profile-");
  for (const name of ["workspace", "home", "tmp"]) mkdirSync(root + "/" + name);
  try {
    const profile = sandboxProfile({
      binary: "/bin/cat",
      workspace: root + "/workspace",
      home: root + "/home",
      temporary: root + "/tmp",
    });
    assert.ok(profile.includes("(deny default)"));
    assert.ok(profile.includes('(allow process-exec (literal "/bin/cat"))'));
    assert.ok(!profile.includes("/Users/"));
    assert.ok(
      !profile.includes('(allow file-write* (subpath "' + root + '/workspace"'),
    );
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});
test("agent cannot execute without explicit authorization and dedicated credentials", async () => {
  const saved = process.env.OPSGUARD_AGENT_AUTHORIZED;
  delete process.env.OPSGUARD_AGENT_AUTHORIZED;
  try {
    await assert.rejects(
      investigate({}),
      /authorization|containment|credentials/i,
    );
  } finally {
    if (saved !== undefined) process.env.OPSGUARD_AGENT_AUTHORIZED = saved;
  }
});
test(
  "real OS containment probe (no credentials, no AI call)",
  { skip: process.env.OPSGUARD_SANDBOX_TEST !== "1" },
  () => {
    assert.equal(containmentSelfTest(), true);
  },
);

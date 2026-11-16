import { realpathSync } from "node:fs";
import { fileURLToPath } from "node:url";
const packageRoot = fileURLToPath(
  new URL(
    "./node_modules/@openai/codex-darwin-arm64/vendor/aarch64-apple-darwin/",
    import.meta.url,
  ),
);
export function nativeCodex() {
  return realpathSync(packageRoot + "bin/codex");
}
export function sandboxProfile({ binary, workspace, home, temporary }) {
  const quote = (value) => JSON.stringify(realpathSync(value));
  return `(version 1)
(deny default)
(allow file-read-metadata)
(allow process-info* sysctl-read mach-lookup signal)
(allow file-read* (subpath "/System") (subpath "/usr/lib") (subpath "/usr/share") (subpath "/private/etc/ssl") (literal "/private/etc/hosts") (literal "/private/etc/resolv.conf") (literal "/private/etc/localtime") (subpath "/Library/Apple") (literal "/dev/null") (literal "/dev/urandom") (literal "/dev/random") (subpath "/private/var/db/timezone") (literal ${quote(binary)}) (subpath ${quote(workspace)}) (subpath ${quote(home)}) (subpath ${quote(temporary)}))
(allow file-write* (subpath ${quote(home)}) (subpath ${quote(temporary)}) (literal "/dev/null"))
(allow process-exec (literal ${quote(binary)}))
(allow process-fork)
(allow network-outbound)
`;
}

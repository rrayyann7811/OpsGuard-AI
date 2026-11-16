import { spawnSync } from 'node:child_process';
const hosted = process.env.NEXT_PUBLIC_HOSTED_API === 'true';
const result = spawnSync(
  process.execPath,
  ['node_modules/next/dist/bin/next', 'build', '--webpack'],
  {
    stdio: 'inherit',
    env: { ...process.env, NEXT_PUBLIC_DEMO_MODE: hosted ? 'false' : 'true' },
  },
);
process.exit(result.status ?? 1);

import { defineConfig } from 'vitest/config';
import { fileURLToPath } from 'node:url';
export default defineConfig({
  test: {
    maxWorkers: 1,
    env: { NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000' },
  },
  resolve: { alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) } },
});

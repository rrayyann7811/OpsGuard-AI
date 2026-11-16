// @vitest-environment jsdom
import { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { AIReadinessPanel } from './ai-readiness';
import { InvestigationSummaryPanel } from './investigation-summary';
let host: HTMLDivElement, root: Root;
const state = {
  backend: 'local-ollama',
  model: 'llama3.2:3b',
  model_configured: true,
  execution_enabled: false,
  action_token_configured: false,
  server_reachable: true,
  model_installed: true,
  memory_guard: 'blocked',
  memory: {
    available_estimate_bytes: 2 * 1024 ** 3,
    required_estimate_bytes: 3565960695,
    method: 'synthetic fixture',
  },
  verification_status: 'pending',
  live_inference_verified: false,
  checked_at: '2026-11-16T10:00:00Z',
  error_code: 'OLLAMA_MEMORY_INSUFFICIENT',
};
beforeEach(() => {
  vi.stubGlobal('IS_REACT_ACT_ENVIRONMENT', true);
  host = document.createElement('div');
  document.body.append(host);
  root = createRoot(host);
});
afterEach(async () => {
  await act(async () => root.unmount());
  host.remove();
  vi.unstubAllGlobals();
});
it('distinguishes configuration, connectivity, installation and blocked memory without implying verified inference', async () => {
  const fetcher = vi.fn(async () => ({ ok: true, json: async () => state }));
  vi.stubGlobal('fetch', fetcher);
  await act(async () => root.render(<AIReadinessPanel />));
  expect(host.textContent).toContain('llama3.2:3b');
  expect(host.textContent).toContain('Reachable on loopback');
  expect(host.textContent).toContain('Verified by read-only inventory');
  expect(host.textContent).toContain('Blocked');
  expect(host.textContent).toContain('3.32 GiB');
  expect(host.textContent).toContain('Configured; not inference verified');
  expect(host.textContent).toContain('Disabled — safe for website testing');
  expect(host.textContent).toContain('Pending — no successful live verification recorded');
  expect(fetcher).toHaveBeenCalledTimes(1);
  await act(async () => host.querySelector('button')!.click());
  expect(fetcher).toHaveBeenCalledTimes(2);
  expect(fetcher.mock.calls).toHaveLength(2);
});
it('shows unavailable stages honestly rather than failed installation or successful memory status', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => ({
      ok: true,
      json: async () => ({
        ...state,
        server_reachable: false,
        model_installed: null,
        memory_guard: 'not_checked',
        memory: null,
        error_code: 'OLLAMA_UNAVAILABLE',
      }),
    })),
  );
  await act(async () => root.render(<AIReadinessPanel />));
  expect(host.textContent).toContain('Unavailable');
  expect(host.textContent).toContain('Not checked');
  expect(host.textContent).not.toContain('Verified by read-only inventory');
  expect(host.textContent).not.toContain('Passed at this check');
});
it('passing preflight remains unverified, and fake diagnostic responses are explicitly marked', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => ({
      ok: true,
      json: async () => ({
        ...state,
        memory_guard: 'passed',
        error_code: null,
        diagnostic_mode: 'test-double',
      }),
    })),
  );
  await act(async () => root.render(<AIReadinessPanel />));
  expect(host.textContent).toContain('Passed at this check only');
  expect(host.textContent).toContain('TEST DOUBLE');
  expect(host.textContent).toContain('Real inference verification pending');
});
it('offers readiness recovery after an API failure', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => {
      throw new Error('offline');
    }),
  );
  await act(async () => root.render(<AIReadinessPanel />));
  expect(host.querySelector('[role="alert"]')).not.toBeNull();
  expect(host.querySelector('button')?.disabled).toBe(false);
});
it('uses actual investigation counts without a success-rate percentage or fictional diagnoses', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => ({
      ok: true,
      json: async () => ({ total: 5, running: 1, completed: 2, failed: 1, cancelled: 1 }),
    })),
  );
  await act(async () => root.render(<InvestigationSummaryPanel />));
  expect(host.textContent).toContain('Completed');
  expect(host.textContent).toContain('All-time persisted jobs');
  expect(host.textContent).toContain('Test doubles and genuine');
  expect(host.textContent).not.toContain('%');
  expect(host.querySelector('a')?.getAttribute('href')).toBe('/investigations');
});

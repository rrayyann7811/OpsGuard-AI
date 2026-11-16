// @vitest-environment jsdom
import { act } from 'react';
import { createRoot } from 'react-dom/client';
import { afterEach, expect, it, vi } from 'vitest';
vi.mock('@/lib/runtime-mode', () => ({ isPublicDemo: false, isHostedApi: true }));
import { HealthProvider } from './health-provider';
import { ConnectionPanel } from './connection-panel';
import { KnowledgePage } from './knowledge-page';
import { AIReadinessPanel } from './ai-readiness';
import { InvestigateAction } from './investigations-page';
import { fetchHealth } from '../lib/health';
import { investigationAction } from '../lib/investigations';
afterEach(() => vi.unstubAllGlobals());
it('uses a real HTTP response for stateless connectivity and never claims database persistence', async () => {
  vi.stubGlobal('IS_REACT_ACT_ENVIRONMENT', true);
  const fetch = vi.fn(async () => ({
    ok: true,
    json: async () => ({
      status: 'healthy',
      service: 'OpsGuard AI',
      version: '0.1.0',
      environment: 'production',
      mode: 'hosted-readonly',
      database: 'not_configured',
    }),
  }));
  vi.stubGlobal('fetch', fetch);
  const host = document.createElement('div');
  const root = createRoot(host);
  try {
    await act(async () =>
      root.render(
        <HealthProvider>
          <ConnectionPanel />
          <KnowledgePage />
          <AIReadinessPanel />
          <InvestigateAction incidentId="synthetic" />
        </HealthProvider>,
      ),
    );
    expect(fetch).toHaveBeenCalledTimes(1);
    expect(host.textContent).toContain('Backend is connected');
    expect(host.textContent).toContain('Not configured — stateless');
    expect(host.textContent).toContain('Historical knowledge unavailable');
    expect(host.textContent).toContain('AI execution disabled');
    expect(host.querySelector('input[type="password"]')).toBeNull();
    expect(host.textContent).not.toContain('API and SQLite are responding');
  } finally {
    await act(async () => root.unmount());
  }
});
it('does not fabricate connectivity or allow privileged actions', async () => {
  const fetch = vi.fn(async () => {
    throw new TypeError('offline');
  });
  vi.stubGlobal('fetch', fetch);
  await expect(fetchHealth()).rejects.toThrow('offline');
  await expect(
    investigationAction('/api/anything', '', {}, new AbortController().signal),
  ).rejects.toThrow('disabled');
  expect(fetch).toHaveBeenCalledTimes(1);
});

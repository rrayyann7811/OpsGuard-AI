// @vitest-environment jsdom
import { afterEach, expect, it, vi } from 'vitest';
import { publicDemoData } from './public-demo';
afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
  vi.resetModules();
});
it('filters and details use consistent explicitly synthetic records', () => {
  const page = publicDemoData(
    '/api/incidents?service=payment-service&severity=high&status=OPEN',
  ) as { items: { id: string }[]; total: number };
  expect(page.total).toBe(1);
  expect(page.items[0].id).toMatch(/^DEMO-/);
  expect(publicDemoData('/api/incidents?severity=critical')).toMatchObject({ total: 0 });
  expect(publicDemoData(`/api/incidents/${page.items[0].id}`)).toEqual({ incident: page.items[0] });
  expect(publicDemoData(`/api/incidents/${page.items[0].id}/events`)).toMatchObject({ total: 2 });
  expect(publicDemoData('/api/investigations')).toMatchObject({ total: 0 });
  expect(publicDemoData('/api/services')).toMatchObject({
    items: [{ status: 'Unknown' }, { status: 'Unknown' }, { status: 'Unknown' }],
  });
});
it('all public data and action boundaries avoid HTTP, even with an API origin configured', async () => {
  vi.stubEnv('NEXT_PUBLIC_DEMO_MODE', 'true');
  vi.stubEnv('NEXT_PUBLIC_API_URL', 'https://must-not-be-called.invalid');
  vi.resetModules();
  const fetch = vi.fn(() => {
    throw new Error('Network forbidden');
  });
  vi.stubGlobal('fetch', fetch);
  const { getData } = await import('./monitoring');
  const { fetchHealth } = await import('./health');
  const { searchKnowledge } = await import('./knowledge');
  const { investigationAction } = await import('./investigations');
  const signal = new AbortController().signal;
  for (const path of [
    '/api/incidents',
    '/api/incidents/summary',
    '/api/services',
    '/api/investigations',
    '/api/investigations/configuration',
    '/api/investigations/summary',
    '/api/knowledge/status',
    '/api/knowledge/incidents',
  ])
    await getData(path, signal);
  await expect(fetchHealth()).rejects.toThrow('no backend');
  await expect(searchKnowledge('/api/knowledge/search', {}, signal)).rejects.toThrow('local-only');
  await expect(investigationAction('/api/anything', '', {}, signal)).rejects.toThrow('disabled');
  await expect(getData('/api/not-supported', signal)).rejects.toThrow('unavailable');
  expect(fetch).not.toHaveBeenCalled();
});

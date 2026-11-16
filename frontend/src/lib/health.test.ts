import { afterEach, describe, expect, it, vi } from 'vitest';
import { fetchHealth } from './health';
afterEach(() => vi.unstubAllGlobals());
describe('health client', () => {
  it('accepts the backend health contract', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            status: 'healthy',
            service: 'OpsGuard AI',
            version: '0.1.0',
            environment: 'development',
            database: 'connected',
          }),
        ),
      ),
    );
    expect((await fetchHealth()).database).toBe('connected');
  });
  it('reports unsuccessful backend responses', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('', { status: 503 })));
    await expect(fetchHealth()).rejects.toThrow('HTTP 503');
  });
  it('rejects malformed health responses', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(new Response(JSON.stringify({ status: 'healthy' }))),
    );
    await expect(fetchHealth()).rejects.toThrow('Unexpected backend health response');
  });
  it('reports network failures', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')));
    await expect(fetchHealth()).rejects.toThrow('Failed to fetch');
  });
});

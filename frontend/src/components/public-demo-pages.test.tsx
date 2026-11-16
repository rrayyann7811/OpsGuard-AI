// @vitest-environment jsdom
import { act } from 'react';
import { createRoot } from 'react-dom/client';
import { expect, it, vi } from 'vitest';
vi.mock('@/lib/runtime-mode', () => ({ isPublicDemo: true, isHostedApi: false }));
vi.mock('next/navigation', () => ({ usePathname: () => '/' }));
import { Shell } from './shell';
import { Dashboard } from './dashboard';
for (const slug of [
  '',
  'incidents',
  'services',
  'investigations',
  'knowledge',
  'analytics',
  'settings',
]) {
  it(`public ${slug || 'overview'} renders without network or local API links`, async () => {
    vi.stubGlobal('IS_REACT_ACT_ENVIRONMENT', true);
    const fetch = vi.fn(() => {
      throw new Error('Network forbidden');
    });
    vi.stubGlobal('fetch', fetch);
    HTMLDialogElement.prototype.close = function () {
      this.open = false;
    };
    const host = document.createElement('div');
    document.body.append(host);
    const root = createRoot(host);
    try {
      await act(async () =>
        root.render(
          <Shell>
            <Dashboard slug={slug} />
          </Shell>,
        ),
      );
      expect(host.textContent).toContain('Public demonstration — synthetic data only');
      expect(host.textContent).not.toContain('Live local monitoring');
      expect(host.textContent).not.toContain('Backend connected');
      expect(host.querySelector('a[href*="127.0.0.1"]')).toBeNull();
      if (slug === 'knowledge')
        expect((host.querySelector('button[type="submit"]') as HTMLButtonElement).disabled).toBe(
          true,
        );
      if (slug === 'settings') {
        expect(host.textContent).toContain('AI execution disabled');
        expect(host.querySelector('input[type="password"]')).toBeNull();
      }
      expect(fetch).not.toHaveBeenCalled();
    } finally {
      await act(async () => root.unmount());
      host.remove();
      vi.unstubAllGlobals();
    }
  });
}

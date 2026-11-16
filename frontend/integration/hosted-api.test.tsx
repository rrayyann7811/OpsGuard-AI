// @vitest-environment jsdom
import { act } from 'react';
import { createRoot } from 'react-dom/client';
import { expect, test } from 'vitest';
import { Dashboard } from '../src/components/dashboard';
import { HealthProvider } from '../src/components/health-provider';
import { MonitoringProvider } from '../src/components/monitoring-provider';
test.skipIf(!process.env.OPSGUARD_HOSTED_API_TEST_URL)(
  'real hosted API renders connected/stateless and safe empty states',
  async () => {
    Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true });
    const host = document.createElement('div');
    document.body.append(host);
    const root = createRoot(host);
    async function waitFor(text: string) {
      for (let i = 0; i < 100; i++) {
        await act(async () => {
          await new Promise((resolve) => setTimeout(resolve, 50));
        });
        if (host.textContent?.includes(text)) return;
      }
      throw new Error('Missing hosted state: ' + text);
    }
    try {
      for (const [slug, expected] of [
        ['', 'Backend is connected'],
        ['incidents', 'No matching incidents'],
        ['services', 'Monitoring not configured'],
        ['knowledge', 'Historical knowledge unavailable'],
        ['investigations', 'No investigations yet'],
        ['analytics', 'No incident history yet'],
        ['settings', 'AI execution disabled'],
      ]) {
        await act(async () =>
          root.render(
            <HealthProvider>
              <MonitoringProvider>
                <Dashboard slug={slug} />
              </MonitoringProvider>
            </HealthProvider>,
          ),
        );
        await waitFor(expected);
        expect(host.querySelector('input[type="password"]')).toBeNull();
        expect(host.textContent).not.toContain('DEMO-PAY-001');
      }
    } finally {
      await act(async () => root.unmount());
      host.remove();
    }
  },
  30000,
);

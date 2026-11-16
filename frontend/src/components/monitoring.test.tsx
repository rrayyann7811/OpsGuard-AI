// @vitest-environment jsdom
import { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { IncidentDetails, IncidentTable } from './incident-table';
import { MonitoringProvider, MonitoringNotice } from './monitoring-provider';
import { SeverityChart, ServiceIncidentSummary } from './charts';
import { ServiceCards } from './service-cards';
import { incidentPath } from '../lib/monitoring';

const incident = {
  id: 'incident-1',
  title: 'PaymentFailure: payment-service',
  service_name: 'payment-service',
  severity: 'high',
  status: 'OPEN',
  occurrence_count: 2,
  first_seen: '2026-11-14T10:00:00Z',
  last_seen: '2026-11-14T10:01:00Z',
  endpoint: '/payments',
  http_status: 502,
  error_message: 'Processor rejected payment',
  stack_trace: 'at process (app.js:10)',
};
const event = {
  event_id: 'event-1',
  request_id: 'request-1',
  timestamp: incident.last_seen,
  error_message: incident.error_message,
  stack_trace: incident.stack_trace,
  http_status: 502,
  duration_ms: 2,
};
let host: HTMLDivElement, root: Root;
let requests: string[];
async function flush() {
  await act(async () => {
    await Promise.resolve();
  });
}
function mockApi() {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string) => {
      requests.push(url);
      if (url.includes('/summary'))
        return {
          ok: true,
          json: async () => ({
            active: 1,
            critical: 0,
            total: 1,
            resolved: 0,
            by_severity: { high: 1 },
            history: [],
          }),
        };
      if (url.endsWith('/services'))
        return {
          ok: true,
          json: async () => ({
            items: [
              {
                service_name: 'payment-service',
                status: 'Healthy',
                available: true,
                last_attempt: incident.last_seen,
                last_success: incident.last_seen,
                latency_ms: 12,
                consecutive_failures: 0,
                failure_reason: null,
              },
            ],
          }),
        };
      if (url.includes('/events?'))
        return { ok: true, json: async () => ({ items: [event], total: 1 }) };
      if (url.endsWith('/incident-1')) return { ok: true, json: async () => ({ incident }) };
      return { ok: true, json: async () => ({ items: [incident], total: 1 }) };
    }),
  );
}
beforeEach(() => {
  vi.stubGlobal('IS_REACT_ACT_ENVIRONMENT', true);
  vi.useFakeTimers();
  requests = [];
  host = document.createElement('div');
  document.body.append(host);
  root = createRoot(host);
  HTMLDialogElement.prototype.showModal = function () {
    this.open = true;
  };
  HTMLDialogElement.prototype.close = function () {
    this.open = false;
    this.dispatchEvent(new Event('close'));
  };
  mockApi();
});
afterEach(async () => {
  await act(async () => root.unmount());
  host.remove();
  vi.useRealTimers();
  vi.unstubAllGlobals();
});
describe('live incident experience', () => {
  it('renders persisted list, severity/status/service filters and details', async () => {
    await act(async () => root.render(<IncidentTable />));
    await flush();
    expect(host.textContent).toContain(incident.title);
    expect(host.textContent).toContain('2');
    expect(host.textContent).toContain('First: 2026-11-14 10:00:00 UTC');
    expect(host.textContent).toContain('Latest: 2026-11-14 10:01:00 UTC');
    const severity = host.querySelector('[aria-label="Filter severity"]') as HTMLSelectElement;
    await act(async () => {
      severity.value = 'high';
      severity.dispatchEvent(new Event('change', { bubbles: true }));
    });
    await flush();
    expect(requests.at(-1)).toContain('severity=high');
    const status = host.querySelector('[aria-label="Filter status"]') as HTMLSelectElement;
    await act(async () => {
      status.value = 'OPEN';
      status.dispatchEvent(new Event('change', { bubbles: true }));
    });
    await flush();
    expect(requests.at(-1)).toContain('status=OPEN');
    const service = host.querySelector('[aria-label="Filter service"]') as HTMLSelectElement;
    await act(async () => {
      service.value = 'payment-service';
      service.dispatchEvent(new Event('change', { bubbles: true }));
    });
    await flush();
    expect(requests.at(-1)).toContain('service=payment-service');
    await act(async () =>
      (host.querySelector('[aria-label="Inspect incident-1"]') as HTMLButtonElement).click(),
    );
    await flush();
    expect(host.querySelector('dialog')?.open).toBe(true);
    expect(host.textContent).toContain('request-1');
    expect(host.textContent).toContain('at process (app.js:10)');
    expect(host.textContent).toContain('Occurrences: 2');
  });
  it('encodes combined search filters safely', () => {
    const params = new URLSearchParams(
      incidentPath({
        query: 'payment & error',
        severity: 'high',
        status: 'OPEN',
        service: 'payment-service',
        page: 2,
      }).split('?')[1],
    );
    expect(params.get('search')).toBe('payment & error');
    expect(params.get('page')).toBe('2');
  });
  it('shows loading and empty states without sample records', async () => {
    let resolve!: (value: unknown) => void;
    vi.stubGlobal(
      'fetch',
      vi.fn(
        () =>
          new Promise((r) => {
            resolve = r;
          }),
      ),
    );
    await act(async () => root.render(<IncidentTable />));
    expect(host.textContent).toContain('Loading persisted incidents');
    await act(async () => resolve({ ok: true, json: async () => ({ items: [], total: 0 }) }));
    await flush();
    expect(host.textContent).toContain('No matching incidents');
    expect(host.textContent).not.toContain('INC-1042');
  });
  it('shows backend offline state and recovers on bounded polling', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => {
        throw new Error('offline');
      }),
    );
    await act(async () => root.render(<IncidentTable />));
    await flush();
    expect(host.textContent).toContain('offline');
    expect(vi.getTimerCount()).toBe(1);
    mockApi();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(10000);
    });
    await flush();
    expect(host.textContent).toContain(incident.title);
    expect(host.textContent).not.toContain('offline');
  });
  it('polls without refresh and cleans timers when unmounted', async () => {
    await act(async () => root.render(<IncidentTable />));
    await flush();
    expect(requests.length).toBe(1);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(5000);
    });
    expect(requests.length).toBe(2);
    await act(async () => root.render(null));
    expect(vi.getTimerCount()).toBe(0);
  });
  it('renders real service health without uptime claims', async () => {
    await act(async () =>
      root.render(
        <MonitoringProvider>
          <MonitoringNotice />
          <ServiceCards />
        </MonitoringProvider>,
      ),
    );
    await flush();
    expect(host.textContent).toContain('payment-service');
    expect(host.textContent).toContain('Healthy');
    expect(host.textContent).toContain('12 ms');
    expect(host.textContent).not.toContain('99.');
    expect(host.textContent).toContain('Live local monitoring');
  });
  it('details expose actual evidence and paginated event history', async () => {
    await act(async () => root.render(<IncidentDetails id="incident-1" />));
    await flush();
    expect(host.textContent).toContain('Event event-1');
    expect(host.textContent).toContain('HTTP 502');
    expect(host.textContent).toContain('AI reports are read-only hypotheses');
  });
});

it('debounces search input before sending backend filters', async () => {
  await act(async () => root.render(<IncidentTable />));
  await flush();
  const input = host.querySelector('[aria-label="Search incidents"]') as HTMLInputElement;
  await act(async () => {
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')!.set!.call(
      input,
      'payment error',
    );
    input.dispatchEvent(new Event('input', { bubbles: true }));
  });
  expect(requests).toHaveLength(1);
  await act(async () => {
    await vi.advanceTimersByTimeAsync(300);
  });
  expect(requests.at(-1)).toContain('search=payment+error');
});

it('shows detail errors and cleans both detail timers', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => {
      throw new Error('offline');
    }),
  );
  await act(async () => root.render(<IncidentDetails id="incident-1" />));
  await flush();
  expect(host.textContent).toContain('offline');
  expect(vi.getTimerCount()).toBe(2);
  await act(async () => root.render(null));
  expect(vi.getTimerCount()).toBe(0);
});

it('opens the incident list with the selected service from a service-directory link', async () => {
  window.history.replaceState({}, '', '/incidents?service=payment-service');
  try {
    await act(async () => root.render(<IncidentTable />));
    await flush();
    expect((host.querySelector('[aria-label="Filter service"]') as HTMLSelectElement).value).toBe(
      'payment-service',
    );
    expect(requests.at(-1)).toContain('service=payment-service');
  } finally {
    window.history.replaceState({}, '', '/');
  }
});

it('shows a genuine zero-data severity state and service incident summary', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string) => ({
      ok: true,
      json: async () =>
        url.endsWith('/services')
          ? {
              items: [
                {
                  service_name: 'payment-service',
                  incident_summary: { active: 0, resolved: 0, total: 0 },
                },
              ],
            }
          : {
              by_severity: { high: 0 },
              history: [],
              total: 0,
              active: 0,
              critical: 0,
              resolved: 0,
            },
    })),
  );
  await act(async () =>
    root.render(
      <MonitoringProvider>
        <SeverityChart />
        <ServiceIncidentSummary />
      </MonitoringProvider>,
    ),
  );
  await flush();
  expect(host.textContent).toContain('No incidents yet');
  expect(host.textContent).toContain('failed health checks alone do not create incident records');
  expect(host.querySelector('tbody tr')?.textContent).toBe('payment-service000');
});

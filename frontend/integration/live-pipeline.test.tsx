// @vitest-environment jsdom
import { act } from 'react';
import { createRoot } from 'react-dom/client';
import { expect, test } from 'vitest';
import { IncidentTable } from '../src/components/incident-table';
import { MonitoringProvider } from '../src/components/monitoring-provider';
import { Metrics } from '../src/components/metrics';
import { TrafficChart, SeverityChart, ServiceIncidentSummary } from '../src/components/charts';
import { InvestigationSummaryPanel } from '../src/components/investigation-summary';
import { ServiceCards } from '../src/components/service-cards';
import { apiUrl } from '../src/lib/health';

// No fetch mocks: a real Node payment process publishes to a real FastAPI process.
test.skipIf(!process.env.OPSGUARD_LIVE_PAYMENT_URL)(
  'real payment failure → FastAPI → SQLite → React polling and evidence',
  async () => {
    Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true });
    HTMLDialogElement.prototype.showModal = function () {
      this.open = true;
    };
    HTMLDialogElement.prototype.close = function () {
      this.open = false;
      this.dispatchEvent(new Event('close'));
    };
    const host = document.createElement('div');
    document.body.append(host);
    const root = createRoot(host);
    const payment = process.env.OPSGUARD_LIVE_PAYMENT_URL!;
    async function waitFor(predicate: () => boolean, timeout = 14000) {
      const until = Date.now() + timeout;
      while (Date.now() < until) {
        await act(async () => {
          await new Promise((resolve) => setTimeout(resolve, 100));
        });
        if (predicate()) return;
      }
      throw new Error('Live frontend did not update: ' + host.textContent);
    }
    try {
      await act(async () =>
        root.render(
          <MonitoringProvider>
            <Metrics />
            <TrafficChart />
            <SeverityChart />
            <IncidentTable />
            <ServiceCards />
            <div data-testid="service-analytics">
              <ServiceIncidentSummary />
            </div>
            <InvestigationSummaryPanel />
          </MonitoringProvider>,
        ),
      );
      await waitFor(() => Boolean(host.textContent?.includes('No matching incidents')));
      expect(
        (
          await fetch(payment + '/simulate/payment-failure', {
            method: 'POST',
            headers: { 'content-type': 'application/json' },
            body: '{}',
          })
        ).status,
      ).toBe(502);
      await waitFor(() => Boolean(host.textContent?.includes('PaymentFailure: payment-service')));
      await waitFor(() => Boolean(host.textContent?.includes('1 persisted incidents total')));
      await waitFor(() =>
        Boolean(host.querySelector('[aria-label^="Persisted incident events:"]')),
      );
      const first = await (await fetch(apiUrl + '/api/incidents')).json();
      expect(first.total).toBe(1);
      expect(first.items[0].occurrence_count).toBe(1);
      const incident = first.items[0];
      expect(incident).toMatchObject({
        service_name: 'payment-service',
        severity: 'high',
        status: 'OPEN',
        error_type: 'PaymentFailure',
        http_status: 502,
      });
      expect(Number.isNaN(Date.parse(incident.first_seen))).toBe(false);
      expect(Number.isNaN(Date.parse(incident.last_seen))).toBe(false);
      await fetch(payment + '/simulate/payment-failure', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: '{}',
      });
      await waitFor(() => host.querySelector('tbody tr td:nth-child(5)')?.textContent === '2');
      await waitFor(() =>
        Boolean(
          host
            .querySelector('[aria-label^="Persisted incident events:"]')
            ?.getAttribute('aria-label')
            ?.includes(': 2'),
        ),
      );
      expect(
        host
          .querySelector('[aria-label^="Persisted incidents by severity:"]')
          ?.getAttribute('aria-label'),
      ).toContain('high: 1');
      const inspect = host.querySelector('[aria-label^="Inspect "]') as HTMLButtonElement;
      await act(async () => inspect.click());
      await waitFor(() =>
        Boolean(
          host.textContent?.includes('Occurrences: 2') && host.textContent?.includes('Request '),
        ),
      );
      expect(host.textContent).toContain('Simulated payment processor rejection');
      expect(host.querySelector('dialog')?.textContent).toContain(incident.id);
      expect(host.querySelector('dialog')?.textContent).toContain('Error type: PaymentFailure');
      expect(host.querySelector('dialog')?.textContent).toContain('HTTP 502');
      const persisted = await (await fetch(apiUrl + `/api/incidents/${incident.id}`)).json();
      expect(persisted.incident).toMatchObject({
        ...incident,
        occurrence_count: 2,
        last_seen: expect.any(String),
        updated_at: expect.any(String),
      });
      const filtered = await (
        await fetch(apiUrl + '/api/incidents?service=payment-service&severity=high&status=OPEN')
      ).json();
      expect(filtered.items[0]).toEqual(persisted.incident);
      await waitFor(() =>
        Boolean(
          host
            .querySelector('[data-testid="service-analytics"] tbody')
            ?.textContent?.includes('payment-service101'),
        ),
      );
      expect(host.textContent).toContain('No investigations yet');
      const jobs = await (
        await fetch(apiUrl + `/api/investigations?incident_id=${incident.id}`)
      ).json();
      expect(jobs.total).toBe(0);
      expect(host.querySelector('dialog pre')?.textContent).toContain('shared/app.js');
      await waitFor(() => Boolean(host.textContent?.includes('Health endpoint responding')));
      const detail = await (
        await fetch(apiUrl + `/api/incidents/${first.items[0].id}/events`)
      ).json();
      expect(detail.total).toBe(2);
      expect(detail.items[0].event_id).not.toBe(detail.items[1].event_id);
    } finally {
      await act(async () => root.unmount());
      host.remove();
      Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: false });
    }
  },
  40000,
);

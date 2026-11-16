// @vitest-environment jsdom
import { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { KnowledgePage, SimilarHistoricalIncidents } from './knowledge-page';

const historical = {
  id: 'SYN-PAY-004',
  title: 'Fee subtraction introduced payment total regression',
  service_name: 'payment-service',
  severity: 'high',
  synthetic: true,
  root_cause: 'A revision subtracted the fee instead of adding it.',
  resolution: 'Restore integer-cent fee addition.',
  symptoms: 'Totals below base amount.',
  error_type: 'CalculationRegression',
  error_message: 'Payment total violated fee invariant',
  source_ref: 'Original synthetic dataset v1',
  incident_date: '2026-03-04',
  runbook: ['Expect total 10200 for base amount 10000'],
  technology: ['Node.js'],
  code_context: 'amount + Math.round(amount * 0.02)',
  http_status: 500,
};
const match = {
  incident: historical,
  similarity_score: 0.72,
  rank_score: 0.72,
  matched_chunk: 'Fee invariant',
  source_ref: historical.source_ref,
  ranking_signals: [],
};
let host: HTMLDivElement, root: Root, calls: { url: string; options?: RequestInit }[];
function api() {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string, options?: RequestInit) => {
      calls.push({ url, options });
      let data;
      if (url.endsWith('/status'))
        data = {
          status: 'ready',
          mode: 'embedded-local',
          indexed_incidents: 24,
          indexed_chunks: 24,
          source_count: 1,
          last_indexed_at: '2026-11-15T00:00:00Z',
          embedding_model: 'sentence-transformers/all-MiniLM-L6-v2',
          dimension: 384,
          embedding_loaded: false,
          collection: 'opsguard_history_v1',
        };
      else if (options?.method === 'POST')
        data = { items: [match], total: 1, duration_ms: 8.2, ranking: 'semantic' };
      else if (url.includes('/incidents?'))
        data = { items: [historical], total: 1, page: 1, page_size: 6 };
      else data = { incident: historical };
      return { ok: true, json: async () => data };
    }),
  );
}
async function flush() {
  await act(async () => {
    await Promise.resolve();
  });
}
beforeEach(() => {
  vi.stubGlobal('IS_REACT_ACT_ENVIRONMENT', true);
  calls = [];
  api();
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
});
afterEach(async () => {
  await act(async () => root.unmount());
  host.remove();
  vi.unstubAllGlobals();
});
it('renders actual API status and full synthetic historical details', async () => {
  await act(async () => root.render(<KnowledgePage />));
  await flush();
  expect(host.textContent).toContain('24');
  expect(host.textContent).toContain('embedded-local');
  expect(host.textContent).toContain(historical.title);
  expect(host.textContent).toContain('SYNTHETIC');
  await act(async () =>
    (host.querySelector('.knowledge-card .incident-link') as HTMLButtonElement).click(),
  );
  await flush();
  expect(host.querySelector('dialog')?.open).toBe(true);
  expect(host.textContent).toContain(historical.code_context);
  expect(host.textContent).toContain('Expect total 10200');
});
it('submits service-filtered search and displays actual returned cosine scores', async () => {
  await act(async () => root.render(<KnowledgePage />));
  await flush();
  const query = host.querySelector('textarea')!;
  await act(async () => {
    Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, 'value')!.set!.call(
      query,
      'fee regression',
    );
    query.dispatchEvent(new Event('input', { bubbles: true }));
  });
  const filter = host.querySelector(
    '[aria-label="Historical service filter"]',
  ) as HTMLSelectElement;
  await act(async () => {
    filter.value = 'payment-service';
    filter.dispatchEvent(new Event('change', { bubbles: true }));
  });
  await act(async () =>
    host
      .querySelector('form')!
      .dispatchEvent(new Event('submit', { bubbles: true, cancelable: true })),
  );
  await flush();
  const request = calls.find((call) => call.options?.method === 'POST')!;
  expect(JSON.parse(request.options!.body as string)).toMatchObject({
    query: 'fee regression',
    service: 'payment-service',
    ranking: 'semantic',
  });
  expect(host.textContent).toContain('Cosine similarity 0.720');
});
it('shows no-match and retrieval error states', async () => {
  await act(async () => root.render(<SimilarHistoricalIncidents incidentId="current-id" />));
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => ({ ok: true, json: async () => ({ items: [], total: 0 }) })),
  );
  await act(async () => (host.querySelector('button') as HTMLButtonElement).click());
  await flush();
  expect(host.textContent).toContain('No historical matches met');
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => ({ ok: false, status: 503 })),
  );
  await act(async () => (host.querySelector('button') as HTMLButtonElement).click());
  await flush();
  expect(host.textContent).toContain('Historical retrieval is unavailable');
});
it('uses SQLite-based similar endpoint and labels evidence without claiming root cause', async () => {
  await act(async () => root.render(<SimilarHistoricalIncidents incidentId="current-id" />));
  await act(async () => (host.querySelector('button') as HTMLButtonElement).click());
  await flush();
  expect(calls[0].url).toContain('/api/knowledge/similar/current-id');
  expect(host.textContent).toContain('not the verified root cause');
  expect(host.textContent).toContain(historical.resolution);
});
it('shows loading and cancels the pending request on unmount', async () => {
  let signal: AbortSignal | undefined;
  vi.stubGlobal(
    'fetch',
    vi.fn((_url, options) => {
      signal = options.signal;
      return new Promise(() => {});
    }),
  );
  await act(async () => root.render(<SimilarHistoricalIncidents incidentId="current-id" />));
  await act(async () => (host.querySelector('button') as HTMLButtonElement).click());
  expect(host.textContent).toContain('Loading local model');
  await act(async () => root.render(null));
  expect(signal?.aborted).toBe(true);
});

it('sends the owner database query with both filters without treating scores as confidence', async () => {
  await act(async () => root.render(<KnowledgePage />));
  await flush();
  const query = host.querySelector('textarea')!;
  await act(async () => {
    Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, 'value')!.set!.call(
      query,
      'Database connection failed while processing payments',
    );
    query.dispatchEvent(new Event('input', { bubbles: true }));
  });
  for (const [name, value] of [
    ['Historical service filter', 'payment-service'],
    ['Historical severity filter', 'critical'],
  ]) {
    const control = host.querySelector(`[aria-label="${name}"]`) as HTMLSelectElement;
    await act(async () => {
      control.value = value;
      control.dispatchEvent(new Event('change', { bubbles: true }));
    });
  }
  await act(async () =>
    host
      .querySelector('form')!
      .dispatchEvent(new Event('submit', { bubbles: true, cancelable: true })),
  );
  await flush();
  const request = calls.find((call) => call.options?.method === 'POST')!;
  expect(JSON.parse(request.options!.body as string)).toMatchObject({
    query: 'Database connection failed while processing payments',
    service: 'payment-service',
    severity: 'critical',
    ranking: 'semantic',
  });
  expect(host.textContent).toContain('Cosine similarity');
  expect(host.textContent).toContain('not confidence probabilities');
});

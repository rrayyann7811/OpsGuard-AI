// @vitest-environment jsdom
import { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { beforeEach, afterEach, expect, it, vi } from 'vitest';
import { InvestigationsPage, InvestigationDetail, InvestigateAction } from './investigations-page';
const id = '6e2fb960-ae79-4e24-a15b-d778d3cc9e13';
const finding = {
  classification: 'uncertain',
  statement: 'Explicit test-double hypothesis, not AI reasoning.',
  evidence_ids: ['E001'],
};
const job = {
  id,
  incident_id: 'incident-id',
  service_name: 'payment-service',
  status: 'COMPLETED',
  created_at: '2026-11-15T00:00:00Z',
  started_at: '2026-11-15T00:00:00Z',
  completed_at: '2026-11-15T00:00:01Z',
  duration_ms: 1000,
  error_message: null,
  error_code: null,
  root_cause_summary: finding.statement,
  execution_metadata: { mode: 'test-double' },
  evidence: [{ id: 'E001', kind: 'log', content: 'Observed controlled failure' }],
  report: {
    error_summary: 'Test controlled failure',
    suspected_root_cause: finding,
    verified_facts: [],
    explanation: [],
    affected_files: [],
    suspected_commits: [],
    historical_references: [],
    recommended_remediation: [],
    limitations: ['TEST DOUBLE only'],
    confidence: { category: 'INSUFFICIENT_EVIDENCE', reason: 'No source citation' },
  },
};
let host: HTMLDivElement, root: Root, calls: { url: string; options?: RequestInit }[];
function mockApi(available = true, backend = 'test-double') {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string, options?: RequestInit) => {
      calls.push({ url, options });
      let value;
      if (url.includes('/configuration'))
        value = {
          available,
          mode: backend === 'local-ollama' ? 'local-ollama' : 'test-double',
          backend,
          model: backend === 'local-ollama' ? 'tiny:latest' : undefined,
          message: available
            ? 'Explicit deterministic test double.'
            : 'Codex unavailable: missing verified containment.',
        };
      else if (url.includes('/summary'))
        value = {
          total: 1,
          completed: 1,
          running: 0,
          failed: 0,
          cancelled: 0,
          average_duration_ms: 1000,
        };
      else if (url.includes('/events'))
        value = {
          items: [
            { id: 1, timestamp: job.created_at, status: 'COMPLETED', message: 'Report validated' },
          ],
          total: 1,
        };
      else if (url.includes('/investigations?')) value = { items: [job], total: 1 };
      else value = { investigation: job };
      return { ok: true, json: async () => value };
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
  mockApi();
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
it('renders persisted overview/list and opens an explicitly labeled test-double result', async () => {
  await act(async () => root.render(<InvestigationsPage />));
  await flush();
  expect(host.textContent).toContain('Total investigations');
  expect(host.textContent).toContain('1.00 s');
  expect(host.textContent).toContain('TEST DOUBLE');
  await act(async () => (host.querySelector('.incident-link') as HTMLButtonElement).click());
  await flush();
  expect(host.querySelector('dialog')?.open).toBe(true);
  expect(host.textContent).toContain('Observed controlled failure');
  expect(host.textContent).toContain('INSUFFICIENT_EVIDENCE');
});
it('does not offer paid action when Codex containment/configuration is unavailable', async () => {
  mockApi(false);
  await act(async () => root.render(<InvestigateAction incidentId="incident-id" />));
  await flush();
  expect(host.textContent).toContain('missing verified containment');
  expect(host.querySelector('form')).toBeNull();
  expect(calls.some((call) => call.options?.method === 'POST')).toBe(false);
});
it('requires explicit authorization and token, then clears credentials and exposes progress', async () => {
  await act(async () => root.render(<InvestigateAction incidentId="incident-id" />));
  await flush();
  const button = host.querySelector('button[type="submit"]') as HTMLButtonElement;
  expect(button.disabled).toBe(true);
  const token = host.querySelector('input[type="password"]') as HTMLInputElement;
  await act(async () => {
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')!.set!.call(
      token,
      'one-use-token',
    );
    token.dispatchEvent(new Event('input', { bubbles: true }));
    (host.querySelector('input[type="checkbox"]') as HTMLInputElement).click();
  });
  expect(button.disabled).toBe(false);
  await act(async () =>
    host
      .querySelector('form')!
      .dispatchEvent(new Event('submit', { bubbles: true, cancelable: true })),
  );
  await flush();
  const request = calls.find((call) => call.options?.method === 'POST')!;
  expect(request.url).toContain('/api/incidents/incident-id/investigate');
  expect(JSON.parse(request.options!.body as string)).toEqual({ authorize_paid_execution: true });
  expect((request.options!.headers as Record<string, string>).Authorization).toBe(
    'Bearer one-use-token',
  );
  expect(token.value).toBe('');
  expect(host.textContent).toContain('Open investigation progress');
});
it('shows failed investigation without fabricating a report', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string) => ({
      ok: true,
      json: async () =>
        url.includes('/events')
          ? { items: [] }
          : {
              investigation: {
                ...job,
                status: 'FAILED',
                report: null,
                error_code: 'TIMEOUT',
                error_message: 'Execution timed out.',
              },
            },
    })),
  );
  await act(async () => root.render(<InvestigationDetail id={id} />));
  await flush();
  expect(host.textContent).toContain('Execution timed out');
  expect(host.textContent).toContain('No completed AI report');
  expect(host.textContent).not.toContain('Explicit test-double hypothesis');
});
it('shows backend offline errors', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => {
      throw new Error('offline');
    }),
  );
  await act(async () => root.render(<InvestigationsPage />));
  await flush();
  expect(host.textContent).toContain('offline');
  expect(host.textContent).not.toContain('Explicit test-double hypothesis');
});

it('uses explicit local authorization and shows the configured model without paid wording', async () => {
  mockApi(true, 'local-ollama');
  await act(async () => root.render(<InvestigateAction incidentId="incident-id" />));
  await flush();
  expect(host.textContent).toContain('tiny:latest');
  expect(host.textContent).toContain('Authorize one Local AI Investigation');
  expect(host.textContent).not.toContain('paid API usage');
  const token = host.querySelector('input[type="password"]') as HTMLInputElement;
  await act(async () => {
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')!.set!.call(
      token,
      'local-token',
    );
    token.dispatchEvent(new Event('input', { bubbles: true }));
    (host.querySelector('input[type="checkbox"]') as HTMLInputElement).click();
  });
  await act(async () =>
    host
      .querySelector('form')!
      .dispatchEvent(new Event('submit', { bubbles: true, cancelable: true })),
  );
  await flush();
  const request = calls.find((call) => call.options?.method === 'POST')!;
  expect(JSON.parse(request.options!.body as string)).toEqual({ authorize_local_execution: true });
  expect(token.value).toBe('');
});
it('renders local provenance, model and measured response timing', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string) => ({
      ok: true,
      json: async () =>
        url.includes('/events')
          ? { items: [] }
          : {
              investigation: {
                ...job,
                execution_metadata: {
                  mode: 'local-ollama',
                  model: 'tiny:latest',
                  metrics: { prompt_bytes: 5000, output_bytes: 1000, inference_ms: 2500 },
                },
              },
            },
    })),
  );
  await act(async () => root.render(<InvestigationDetail id={id} />));
  await flush();
  expect(host.textContent).toContain('Local AI Investigation');
  expect(host.textContent).toContain('tiny:latest');
  expect(host.textContent).toContain('5000 bytes');
  expect(host.textContent).toContain('2.50 s');
  expect(host.textContent).not.toContain('LOCAL CODEX');
});

it('opens the collected evidence from a validated finding citation', async () => {
  await act(async () => root.render(<InvestigationDetail id={id} />));
  await flush();
  const citation = host.querySelector('a[href="#evidence-E001"]') as HTMLAnchorElement;
  expect(citation).not.toBeNull();
  await act(async () => citation.click());
  expect(host.querySelector('details#evidence-E001')?.hasAttribute('open')).toBe(true);
  expect(host.textContent).toContain('Accepted by schema and evidence-reference validation');
});

it('never presents a nonterminal or failed report payload as accepted analysis', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string) => ({
      ok: true,
      json: async () =>
        url.includes('/events')
          ? { items: [] }
          : {
              investigation: {
                ...job,
                status: 'FAILED',
                error_code: 'OLLAMA_INVALID_EVIDENCE_OR_REPORT',
                error_message: 'Report rejected',
              },
            },
    })),
  );
  await act(async () => root.render(<InvestigationDetail id={id} />));
  await flush();
  expect(host.textContent).toContain('No completed AI report');
  expect(host.textContent).not.toContain('Accepted by schema');
  expect(host.textContent).not.toContain('Root-cause report');
});

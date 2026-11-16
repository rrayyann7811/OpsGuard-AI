// @vitest-environment jsdom
import { act } from 'react';
import { createRoot } from 'react-dom/client';
import { expect, test } from 'vitest';
import { InvestigateAction, InvestigationsPage } from '../src/components/investigations-page';
import { apiUrl } from '../src/lib/health';

test.skipIf(!process.env.OPSGUARD_INVESTIGATION_DEMO_INCIDENT)(
  'incident/RAG/source/Git/UI workflow with explicit execution provenance',
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
    async function waitFor(predicate: () => boolean) {
      const until = Date.now() + (process.env.OPSGUARD_INVESTIGATION_REAL_LOCAL ? 90000 : 30000);
      while (Date.now() < until) {
        await act(async () => {
          await new Promise((resolve) => setTimeout(resolve, 100));
        });
        if (predicate()) return;
      }
      throw new Error('Investigation test workflow did not update: ' + host.textContent);
    }
    try {
      const incident = process.env.OPSGUARD_INVESTIGATION_DEMO_INCIDENT!;
      await act(async () => root.render(<InvestigateAction incidentId={incident} />));
      await waitFor(() => Boolean(host.querySelector('form')));
      expect(host.textContent).toContain(
        process.env.OPSGUARD_INVESTIGATION_REAL_LOCAL ? 'Local AI Investigation' : 'TEST DOUBLE',
      );
      const input = host.querySelector('input[type="password"]') as HTMLInputElement;
      await act(async () => {
        Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')!.set!.call(
          input,
          process.env.OPSGUARD_INVESTIGATION_DEMO_TOKEN,
        );
        input.dispatchEvent(new Event('input', { bubbles: true }));
        (host.querySelector('input[type="checkbox"]') as HTMLInputElement).click();
      });
      await act(async () =>
        host
          .querySelector('form')!
          .dispatchEvent(new Event('submit', { bubbles: true, cancelable: true })),
      );
      await waitFor(() => Boolean(host.textContent?.includes('COMPLETED')));
      const list = await (await fetch(apiUrl + '/api/investigations')).json();
      const job = list.items[0];
      const detail = await (await fetch(apiUrl + '/api/investigations/' + job.id)).json();
      expect(detail.investigation.execution_metadata.mode).toBe(
        process.env.OPSGUARD_INVESTIGATION_REAL_LOCAL ? 'local-ollama' : 'test-double',
      );
      const kinds = new Set(
        detail.investigation.evidence.map((item: { kind: string }) => item.kind),
      );
      expect(kinds).toEqual(
        new Set(
          process.env.OPSGUARD_INVESTIGATION_WITHOUT_EMBEDDINGS
            ? ['log', 'source', 'git']
            : ['log', 'historical', 'source', 'git'],
        ),
      );
      if (process.env.OPSGUARD_INVESTIGATION_WITHOUT_EMBEDDINGS) {
        expect(detail.investigation.report.limitations.join(' ')).toContain(
          'No historical matches',
        );
      }
      expect(
        detail.investigation.evidence.some(
          (item: { commit_sha?: string }) =>
            item.commit_sha === process.env.OPSGUARD_INVESTIGATION_DEMO_SHA,
        ),
      ).toBe(true);
      await act(async () => root.render(<InvestigationsPage />));
      await waitFor(() => Boolean(host.querySelector('.incident-link')));
      await act(async () => (host.querySelector('.incident-link') as HTMLButtonElement).click());
      await waitFor(() => Boolean(host.textContent?.includes('Root-cause report')));
      expect(host.textContent).toContain(
        process.env.OPSGUARD_INVESTIGATION_REAL_LOCAL ? 'Local AI Investigation' : 'TEST DOUBLE',
      );
      expect(host.textContent).toContain('No causal reproduction or hotfix');
      const original = await (await fetch(apiUrl + '/api/incidents/' + incident)).json();
      expect(original.incident.status).toBe('OPEN');
    } finally {
      await act(async () => root.unmount());
      host.remove();
      Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: false });
    }
  },
  process.env.OPSGUARD_INVESTIGATION_REAL_LOCAL ? 150000 : 60000,
);

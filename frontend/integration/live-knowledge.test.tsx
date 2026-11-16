// @vitest-environment jsdom
import { act } from 'react';
import { createRoot } from 'react-dom/client';
import { expect, test } from 'vitest';
import { KnowledgePage, SimilarHistoricalIncidents } from '../src/components/knowledge-page';
import { apiUrl } from '../src/lib/health';

test.skipIf(!process.env.OPSGUARD_LIVE_KNOWLEDGE_ID)(
  'real cached embeddings → persistent Qdrant → FastAPI → historical React UI and similar incident lookup',
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
      const until = Date.now() + 25000;
      while (Date.now() < until) {
        await act(async () => {
          await new Promise((resolve) => setTimeout(resolve, 100));
        });
        if (predicate()) return;
      }
      throw new Error('Historical UI did not update: ' + host.textContent);
    }
    try {
      await act(async () => root.render(<KnowledgePage />));
      await waitFor(() =>
        Boolean(host.textContent?.includes('24') && host.textContent?.includes('embedded-local')),
      );
      const input = host.querySelector('textarea')!;
      await act(async () => {
        Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, 'value')!.set!.call(
          input,
          'Payment fee was subtracted instead of added to the total',
        );
        input.dispatchEvent(new Event('input', { bubbles: true }));
      });
      await act(async () =>
        host
          .querySelector('form')!
          .dispatchEvent(new Event('submit', { bubbles: true, cancelable: true })),
      );
      await waitFor(() =>
        Boolean(
          host.textContent?.includes('backend retrieval') &&
          host.textContent?.includes('Fee subtraction introduced payment total regression'),
        ),
      );
      expect(host.textContent).toContain('Cosine similarity');
      expect(host.textContent).toContain('SYNTHETIC');
      const button = Array.from(host.querySelectorAll('button')).find(
        (item) => item.textContent === 'Inspect historical incident',
      )!;
      await act(async () => button.click());
      await waitFor(() =>
        Boolean(host.querySelector('dialog')?.textContent?.includes('Runbook steps')),
      );
      expect(host.querySelector('dialog')?.textContent).toContain('knowledge/data/incidents.json');
      await act(async () =>
        root.render(
          <SimilarHistoricalIncidents incidentId={process.env.OPSGUARD_LIVE_KNOWLEDGE_ID!} />,
        ),
      );
      await act(async () => (host.querySelector('button') as HTMLButtonElement).click());
      await waitFor(() => Boolean(host.textContent?.includes('SYN-PAY-004')));
      expect(host.textContent).toContain('not the verified root cause');
      const original = await (
        await fetch(apiUrl + '/api/incidents/' + process.env.OPSGUARD_LIVE_KNOWLEDGE_ID)
      ).json();
      expect(original.incident.status).toBe('OPEN');
    } finally {
      await act(async () => root.unmount());
      host.remove();
      Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: false });
    }
  },
  60000,
);

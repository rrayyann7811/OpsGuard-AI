'use client';
import Link from 'next/link';
import { usePolling } from './monitoring-provider';
import { EmptyState, ErrorMessage, LoadingState, Panel } from './ui';
import type { InvestigationSummary as Summary } from '@/lib/investigations';

export function InvestigationSummaryPanel() {
  const state = usePolling<Summary>('/api/investigations/summary');
  return (
    <Panel
      title="Investigation activity"
      description="All-time persisted jobs. Completed means report validation passed, not proven causality."
      action={
        <Link className="text-link" href="/investigations">
          Open investigations
        </Link>
      }
    >
      <div className="readiness-body">
        {state.loading && <LoadingState label="Loading investigation activity…" />}
        {state.error && <ErrorMessage message={state.error} />}
        {state.data && (
          <>
            <dl className="outcome-grid">
              <div>
                <dt>Queued / running</dt>
                <dd>{state.data.running}</dd>
              </div>
              <div>
                <dt>Completed</dt>
                <dd>{state.data.completed}</dd>
              </div>
              <div>
                <dt>Failed</dt>
                <dd>{state.data.failed}</dd>
              </div>
              <div>
                <dt>Cancelled</dt>
                <dd>{state.data.cancelled}</dd>
              </div>
            </dl>
            {!state.data.total && (
              <EmptyState
                title="No investigations yet"
                description="Open an incident to review evidence. Local AI remains optional until you explicitly authorize a run."
              />
            )}
            <p className="field-help">
              Execution provenance is shown on each report. Test doubles and genuine local-model
              results are kept distinct. No automatic remediation.
            </p>
          </>
        )}
      </div>
    </Panel>
  );
}

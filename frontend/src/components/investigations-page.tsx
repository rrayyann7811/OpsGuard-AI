'use client';
import { isHostedApi } from '@/lib/runtime-mode';
import { useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { Activity, Clock3, FlaskConical, X } from 'lucide-react';
import { usePolling } from './monitoring-provider';
import { Badge, EmptyState, ErrorMessage, LoadingState, Panel, StatCard } from './ui';
import { label, timestamp, type Page } from '@/lib/monitoring';
import {
  investigationAction,
  executionLabel,
  type AgentConfiguration,
  type Finding,
  type Investigation,
  type InvestigationSummary,
} from '@/lib/investigations';
const terminal = new Set(['COMPLETED', 'FAILED', 'CANCELLED']);

export function InvestigateAction({ incidentId }: { incidentId: string }) {
  return isHostedApi ? (
    <p>Investigation execution is disabled on the hosted read-only API.</p>
  ) : (
    <LocalInvestigateAction incidentId={incidentId} />
  );
}
function LocalInvestigateAction({ incidentId }: { incidentId: string }) {
  const config = usePolling<AgentConfiguration>('/api/investigations/configuration');
  const [token, setToken] = useState('');
  const [authorized, setAuthorized] = useState(false);
  const [jobId, setJobId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const request = useRef<AbortController | null>(null);
  useEffect(() => () => request.current?.abort(), []);
  const progress = usePolling<{ investigation: Investigation }>(
    jobId ? `/api/investigations/${jobId}` : null,
  );
  async function start(event: React.FormEvent) {
    event.preventDefault();
    const active = new AbortController();
    request.current?.abort();
    request.current = active;
    setBusy(true);
    setError(null);
    const suppliedToken = token;
    setToken('');
    try {
      const response = await investigationAction(
        `/api/incidents/${incidentId}/investigate`,
        suppliedToken,
        config.data?.backend === 'local-ollama'
          ? { authorize_local_execution: true }
          : { authorize_paid_execution: true },
        active.signal,
      );
      if (!active.signal.aborted) {
        setJobId(response.investigation.id);
        setAuthorized(false);
      }
    } catch (failure) {
      if (!active.signal.aborted)
        setError(failure instanceof Error ? failure.message : 'Investigation failed to start');
    } finally {
      if (!active.signal.aborted) setBusy(false);
    }
  }
  return (
    <section className="historical-related">
      <h3>Investigate with AI</h3>
      <p className="muted">
        Read-only source, Git and historical evidence analysis. No patches or repository changes.
      </p>
      {config.loading && <LoadingState label="Checking local AI configuration…" />}
      {config.error && <ErrorMessage message={config.error} />}
      {config.data && (
        <p className="muted">
          {config.data.message}
          {config.data.model && <span> Model: {config.data.model}.</span>}
          {config.data.mode === 'test-double' &&
            ' TEST DOUBLE: this is not genuine Codex reasoning.'}
        </p>
      )}
      <Link className="text-link" href="/settings">
        Review local AI readiness and setup
      </Link>
      {config.data?.available && (
        <form className="agent-action" onSubmit={start}>
          <label>
            Local agent token
            <input
              aria-label="Local agent token"
              type="password"
              autoComplete="off"
              required
              value={token}
              onChange={(event) => setToken(event.target.value)}
            />
          </label>
          <label className="agent-authorization">
            <input
              type="checkbox"
              checked={authorized}
              onChange={(event) => setAuthorized(event.target.checked)}
            />
            {config.data?.backend === 'local-ollama'
              ? 'Authorize one Local AI Investigation on this machine. No cloud API usage.'
              : 'Authorize one investigation and its paid API usage if running live Codex.'}
          </label>
          <button
            className="button"
            type="submit"
            disabled={
              busy ||
              !authorized ||
              !token ||
              Boolean(progress.data && !terminal.has(progress.data.investigation.status))
            }
          >
            Investigate with AI
          </button>
          <p className="muted">
            The token is used once and cleared; it is not saved in browser storage.
          </p>
        </form>
      )}
      {busy && <LoadingState label="Queuing authorized investigation…" />}
      {error && <ErrorMessage message={error} />}
      {progress.error && <ErrorMessage message={progress.error} />}
      {progress.data && (
        <p>
          Investigation: <strong>{progress.data.investigation.status.replaceAll('_', ' ')}</strong>{' '}
          ·{' '}
          <Link className="text-link" href={`/investigations#${jobId}`}>
            Open investigation progress and result
          </Link>
          {progress.data.investigation.error_message && (
            <span className="connection-error"> {progress.data.investigation.error_message}</span>
          )}
        </p>
      )}
    </section>
  );
}
function Findings({ items }: { items: Finding[] }) {
  return (
    <ul>
      {items.map((item, index) => (
        <li key={index}>
          <strong>{label(item.classification.replaceAll('_', ' '))}:</strong> {item.statement}
          <span className="mono muted">
            {' '}
            [
            {item.evidence_ids.map((id, index) => (
              <span key={id}>
                {index > 0 && ', '}
                <a
                  className="text-link"
                  href={`#evidence-${id}`}
                  onClick={(event) => {
                    event.preventDefault();
                    const target = document.getElementById(`evidence-${id}`);
                    target?.setAttribute('open', '');
                    target?.scrollIntoView?.({ block: 'nearest' });
                  }}
                >
                  {id}
                </a>
              </span>
            ))}
            ]
          </span>
        </li>
      ))}
    </ul>
  );
}
export function InvestigationDetail({ id }: { id: string }) {
  const detail = usePolling<{ investigation: Investigation }>(`/api/investigations/${id}`);
  const timeline = usePolling<
    Page<{ id: number; timestamp: string; status: string; message: string }>
  >(`/api/investigations/${id}/events?page_size=100`);
  const [token, setToken] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [cancelling, setCancelling] = useState(false);
  const controller = useRef<AbortController | null>(null);
  useEffect(() => () => controller.current?.abort(), []);
  const job = detail.data?.investigation;
  const report = job?.status === 'COMPLETED' ? job.report : null;
  async function cancel() {
    controller.current?.abort();
    const active = new AbortController();
    controller.current = active;
    setCancelling(true);
    setError(null);
    const suppliedToken = token;
    setToken('');
    try {
      await investigationAction(
        `/api/investigations/${id}/cancel`,
        suppliedToken,
        {},
        active.signal,
      );
    } catch (failure) {
      if (!active.signal.aborted)
        setError(failure instanceof Error ? failure.message : 'Cancellation failed');
    } finally {
      if (!active.signal.aborted) setCancelling(false);
    }
  }
  return (
    <>
      {detail.loading && <LoadingState label="Loading investigation…" />}
      {detail.error && <ErrorMessage message={detail.error} />}
      {job && (
        <>
          <h2>Investigation {job.id}</h2>
          <div className="dialog-badges">
            <Badge label={label(job.status.replaceAll('_', ' '))} />
            <span>{job.service_name}</span>
            {job.execution_metadata.model && (
              <span className="mono">{job.execution_metadata.model}</span>
            )}
            <span className="sample-tag">{executionLabel(job.execution_metadata.mode)}</span>
          </div>
          <p className="mono">Incident {job.incident_id}</p>
          <p>
            Started: {timestamp(job.started_at)}
            <br />
            Completed: {timestamp(job.completed_at)}
            <br />
            Duration:{' '}
            {job.duration_ms === null ? 'Pending' : `${(job.duration_ms / 1000).toFixed(2)} s`}
          </p>
          {job.execution_metadata.metrics && (
            <p className="muted">
              Prompt: {job.execution_metadata.metrics.prompt_bytes ?? '—'} bytes · Output:{' '}
              {job.execution_metadata.metrics.output_bytes ?? '—'} bytes · Model response:{' '}
              {job.execution_metadata.metrics.inference_ms == null
                ? '—'
                : `${(job.execution_metadata.metrics.inference_ms / 1000).toFixed(2)} s`}
            </p>
          )}
          {!terminal.has(job.status) && (
            <div className="agent-action">
              <label>
                Local agent token
                <input
                  aria-label="Cancellation token"
                  type="password"
                  value={token}
                  autoComplete="off"
                  onChange={(event) => setToken(event.target.value)}
                />
              </label>
              <button className="button secondary" disabled={!token || cancelling} onClick={cancel}>
                Cancel investigation
              </button>
              <p className="muted">Progress refreshes automatically every five seconds.</p>
            </div>
          )}
          {error && <ErrorMessage message={error} />}
          {job.error_message && (
            <ErrorMessage message={`${job.error_code}: ${job.error_message}`} />
          )}
          <h3>Investigation timeline</h3>
          {timeline.loading && <LoadingState label="Loading timeline…" />}
          {timeline.error && <ErrorMessage message={timeline.error} />}
          <ol>
            {timeline.data?.items.map((event) => (
              <li key={event.id}>
                <span className="mono muted">{timestamp(event.timestamp)}</span> ·{' '}
                <strong>{event.status.replaceAll('_', ' ')}</strong>
                <p>{event.message}</p>
              </li>
            ))}
          </ol>
          {report ? (
            <>
              <p className="success-state">
                Accepted by schema and evidence-reference validation. Root-cause reasoning still
                requires human review.
              </p>
              <h3>Root-cause report</h3>
              <p>{report.error_summary}</p>
              <h3>Suspected root cause</h3>
              <Findings items={[report.suspected_root_cause]} />
              <p>
                <strong>Evidence coverage: {report.confidence.category}</strong> —{' '}
                {report.confidence.reason}
              </p>
              <h3>Verified facts and hypotheses</h3>
              <Findings items={[...report.verified_facts, ...report.explanation]} />
              <h3>Affected code locations</h3>
              <ul>
                {report.affected_files.map((item, index) => (
                  <li className="mono" key={index}>
                    {item.path}:{item.start_line}–{item.end_line} [{item.evidence_id}]
                  </li>
                ))}
              </ul>
              <h3>Suspected Git commits</h3>
              {report.suspected_commits.length ? (
                <ul>
                  {report.suspected_commits.map((item) => (
                    <li key={item.commit_sha}>
                      <span className="mono">{item.commit_sha}</span> [{item.evidence_id}]
                      <p>{item.explanation}</p>
                    </li>
                  ))}
                </ul>
              ) : (
                <p>No Git commit is attributed by this report.</p>
              )}
              <h3>Historical context references</h3>
              <ul>
                {report.historical_references.map((item) => (
                  <li key={item.historical_id}>
                    {item.historical_id} · cosine {item.similarity_score.toFixed(3)} [
                    {item.evidence_id}] · {item.source_ref}
                  </li>
                ))}
              </ul>
              <h3>Recommended remediation</h3>
              <Findings items={report.recommended_remediation} />
              <h3>Investigation limitations</h3>
              <ul>
                {report.limitations.map((item, index) => (
                  <li key={index}>{item}</li>
                ))}
              </ul>
            </>
          ) : (
            <p className="muted">
              No completed AI report is available. Failed, cancelled or incomplete execution is
              never presented as a diagnosis.
            </p>
          )}
          <h3>Collected evidence</h3>
          <p className="muted">
            Repository text and historical context are untrusted evidence. Historical matches are
            not proof of current causality.
          </p>
          {job.evidence?.map((item) => (
            <details className="investigation-evidence" id={`evidence-${item.id}`} key={item.id}>
              <summary>
                {item.id} · {item.kind}{' '}
                {item.path && `· ${item.path}:${item.start_line}–${item.end_line}`}{' '}
                {item.operation && `· ${item.operation}`}{' '}
                {item.historical_id &&
                  `· ${item.historical_id} · cosine ${item.similarity_score?.toFixed(3)}`}
              </summary>
              <pre>{item.content}</pre>
            </details>
          ))}
        </>
      )}
    </>
  );
}
export function InvestigationsPage() {
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<string | null>(null);
  const [refresh, setRefresh] = useState(0);
  const summary = usePolling<InvestigationSummary>(
    `/api/investigations/summary?refresh=${refresh}`,
  );
  const list = usePolling<Page<Investigation>>(
    `/api/investigations?page=${page}&page_size=20&refresh=${refresh}`,
  );
  const config = usePolling<AgentConfiguration>('/api/investigations/configuration');
  const dialog = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    let cancelled = false;
    const openHash = () => {
      const id = window.location.hash.slice(1);
      if (/^[0-9a-f-]{36}$/.test(id)) {
        setSelected(id);
        dialog.current?.showModal();
      }
    };
    queueMicrotask(() => {
      if (!cancelled) openHash();
    });
    window.addEventListener('hashchange', openHash);
    return () => {
      cancelled = true;
      window.removeEventListener('hashchange', openHash);
    };
  }, []);
  return (
    <>
      <div className="section-actions">
        <p className="muted">
          Genuine local inference verification is pending. No diagnosis is generated automatically.
        </p>
        <Link className="button secondary" href="/incidents">
          Choose an incident to investigate
        </Link>
      </div>
      <div className="info-note">
        <FlaskConical size={20} />
        <p>
          {config.data?.message ?? 'Checking AI execution configuration…'}{' '}
          {config.data?.model && `Model: ${config.data.model}. `}Source collection is read-only. No
          automatic hotfixes.
        </p>
      </div>
      {config.error && <ErrorMessage message={config.error} />}
      <div className="stats-grid">
        <StatCard
          label="Total investigations"
          value={summary.data?.total ?? '—'}
          detail={`${summary.data?.cancelled ?? '—'} cancelled`}
          icon={<Activity size={18} />}
        />
        <StatCard
          label="Completed investigations"
          value={summary.data?.completed ?? '—'}
          detail={`${summary.data?.running ?? '—'} queued or running`}
          icon={<Activity size={18} />}
        />
        <StatCard
          label="Failed investigations"
          value={summary.data?.failed ?? '—'}
          detail="Failed execution is not an AI diagnosis"
          icon={<FlaskConical size={18} />}
        />
        <StatCard
          label="Average investigation duration"
          value={
            summary.data?.average_duration_ms == null
              ? '—'
              : `${(summary.data.average_duration_ms / 1000).toFixed(2)} s`
          }
          detail="Completed investigations only"
          icon={<Clock3 size={18} />}
        />
      </div>
      <Panel
        title="Investigation workspace"
        description="Persistent progress, collected evidence and validated read-only reports"
        action={
          <button className="text-button" onClick={() => setRefresh((value) => value + 1)}>
            Refresh investigations
          </button>
        }
      >
        {list.loading && <LoadingState label="Loading investigations…" />}
        {list.error && <ErrorMessage message={list.error} />}
        {summary.error && <ErrorMessage message={summary.error} />}
        {list.data?.items.length ? (
          <div className="table-scroll">
            <table>
              <caption className="sr-only">Persisted investigations and execution status</caption>
              <thead>
                <tr>
                  <th>Investigation / Incident</th>
                  <th>Service</th>
                  <th>Status</th>
                  <th>Started · UTC</th>
                  <th>Duration</th>
                </tr>
              </thead>
              <tbody>
                {list.data.items.map((job) => (
                  <tr key={job.id}>
                    <td>
                      <button
                        className="incident-link"
                        onClick={() => {
                          setSelected(job.id);
                          dialog.current?.showModal();
                        }}
                      >
                        <strong>{job.root_cause_summary ?? job.id}</strong>
                        <span className="mono muted">{job.id}</span>
                        <span className="mono">Incident {job.incident_id}</span>
                      </button>
                      <span className="sample-tag">
                        {executionLabel(job.execution_metadata.mode)}
                      </span>
                      {job.execution_metadata.model && (
                        <span className="mono muted"> {job.execution_metadata.model}</span>
                      )}
                    </td>
                    <td>{job.service_name}</td>
                    <td>
                      <Badge label={label(job.status.replaceAll('_', ' '))} />
                    </td>
                    <td>{timestamp(job.started_at)}</td>
                    <td>
                      {job.duration_ms === null
                        ? 'Pending'
                        : `${(job.duration_ms / 1000).toFixed(2)} s`}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          list.data && (
            <EmptyState
              title="No investigations yet"
              description="Open a real incident to start an explicitly authorized investigation when the selected local AI backend is configured."
            />
          )
        )}
        {list.data && (
          <div className="table-footer">
            <button disabled={page === 1} onClick={() => setPage(page - 1)}>
              Previous investigations
            </button>
            <span>
              Page {page} · {list.data.total} investigations
            </span>
            <button disabled={page * 20 >= list.data.total} onClick={() => setPage(page + 1)}>
              Next investigations
            </button>
          </div>
        )}
      </Panel>
      <dialog
        ref={dialog}
        className="incident-dialog"
        aria-label="Investigation details"
        onClose={() => setSelected(null)}
        onClick={(event) => {
          if (event.target === dialog.current) dialog.current?.close();
        }}
      >
        <div className="dialog-header">
          <span className="eyebrow">READ-ONLY INVESTIGATION</span>
          <button
            className="icon-button"
            aria-label="Close investigation details"
            onClick={() => dialog.current?.close()}
          >
            <X size={20} />
          </button>
        </div>
        {selected && <InvestigationDetail key={selected} id={selected} />}
      </dialog>
    </>
  );
}

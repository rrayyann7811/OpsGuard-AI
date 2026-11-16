'use client';
import { useEffect, useRef, useState } from 'react';
import { ArrowUpRight, Search, X } from 'lucide-react';
import {
  incidentPath,
  label,
  timestamp,
  type Incident,
  type IncidentEvent,
  type Page,
} from '@/lib/monitoring';
import { InvestigateAction } from './investigations-page';
import { SimilarHistoricalIncidents } from './knowledge-page';
import { usePolling } from './monitoring-provider';
import { Badge, EmptyState, ErrorMessage, LoadingState } from './ui';

export function IncidentDetails({ id }: { id: string }) {
  const detail = usePolling<{ incident: Incident }>(`/api/incidents/${id}`);
  const [page, setPage] = useState(1);
  const events = usePolling<Page<IncidentEvent>>(
    `/api/incidents/${id}/events?page=${page}&page_size=10`,
  );
  const item = detail.data?.incident;
  return (
    <>
      {detail.loading && <LoadingState label="Loading incident evidence…" />}
      {detail.error && <ErrorMessage message={detail.error} />}
      {item && (
        <>
          <h2 id="incident-title">{item.title}</h2>
          <div className="dialog-badges">
            <Badge label={label(item.severity)} />
            <Badge label={label(item.status)} />
            <span>{item.service_name}</span>
          </div>
          <p className="mono">Incident {item.id}</p>
          <p>
            First detected: {timestamp(item.first_seen)}
            <br />
            Most recent: {timestamp(item.last_seen)}
            <br />
            Occurrences: {item.occurrence_count}
          </p>
          <p>
            HTTP {item.http_status} · {item.endpoint}
            <br />
            Error type: {item.error_type}
          </p>
          <h3>Error evidence</h3>
          <pre>
            {item.error_message}
            {item.stack_trace ? `\n\n${item.stack_trace}` : '\nNo stack trace supplied.'}
          </pre>
          <InvestigateAction incidentId={id} />
          <SimilarHistoricalIncidents incidentId={id} />
          <h3>Related events</h3>
          {events.loading && <LoadingState label="Loading event history…" />}
          {events.error && <ErrorMessage message={events.error} />}
          {events.data?.items.map((event) => (
            <div className="info-note" key={event.event_id}>
              <div>
                <p>
                  {timestamp(event.timestamp)} · HTTP {event.http_status} · {event.duration_ms} ms
                </p>
                <p className="mono">
                  Request {event.request_id}
                  <br />
                  Event {event.event_id}
                </p>
                <pre>
                  {event.error_message}
                  {event.stack_trace ? `\n${event.stack_trace}` : ''}
                </pre>
              </div>
            </div>
          ))}
          {events.data && !events.data.items.length && <p>No related events.</p>}
          {events.data && (
            <div className="table-footer">
              <button disabled={page === 1} onClick={() => setPage(page - 1)}>
                Previous events
              </button>
              <span>
                Page {page} · {events.data.total} events
              </span>
              <button disabled={page * 10 >= events.data.total} onClick={() => setPage(page + 1)}>
                Next events
              </button>
            </div>
          )}
          <p className="muted">
            AI reports are read-only hypotheses, not automatic resolutions. Status changes require
            the explicitly enabled local management API.
          </p>
        </>
      )}
    </>
  );
}
export function IncidentTable({ compact = false }: { compact?: boolean }) {
  const [query, setQuery] = useState('');
  const [search, setSearch] = useState('');
  useEffect(() => {
    if (query === search) return;
    const timer = setTimeout(() => setSearch(query), 300);
    return () => clearTimeout(timer);
  }, [query, search]);
  const [severity, setSeverity] = useState('');
  const [status, setStatus] = useState('');
  const [service, setService] = useState('');
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<string | null>(null);
  const dialog = useRef<HTMLDialogElement>(null);
  const result = usePolling<Page<Incident>>(
    incidentPath({ query: search, severity, status, service, page }),
  );
  useEffect(() => {
    if (compact) return;
    const selectedService = new URLSearchParams(window.location.search).get('service');
    let active = true;
    queueMicrotask(() => {
      if (
        active &&
        selectedService &&
        ['user-service', 'order-service', 'payment-service'].includes(selectedService)
      )
        setService(selectedService);
    });
    return () => {
      active = false;
    };
  }, [compact]);
  const rows = compact ? result.data?.items.slice(0, 4) : result.data?.items;
  function inspect(id: string) {
    setSelected(id);
    dialog.current?.showModal();
  }
  return (
    <>
      {!compact && (
        <div className="filter-bar">
          <label className="search-input">
            <Search size={16} />
            <input
              aria-label="Search incidents"
              placeholder="Search incidents, IDs, or services…"
              value={query}
              maxLength={200}
              onChange={(event) => {
                setQuery(event.target.value);
                setPage(1);
              }}
            />
          </label>
          <select
            aria-label="Filter severity"
            value={severity}
            onChange={(event) => {
              setSeverity(event.target.value);
              setPage(1);
            }}
          >
            <option value="">All severities</option>
            {['critical', 'high', 'medium', 'low'].map((value) => (
              <option key={value} value={value}>
                {label(value)}
              </option>
            ))}
          </select>
          <select
            aria-label="Filter status"
            value={status}
            onChange={(event) => {
              setStatus(event.target.value);
              setPage(1);
            }}
          >
            <option value="">All statuses</option>
            {['OPEN', 'INVESTIGATING', 'RESOLVED'].map((value) => (
              <option key={value} value={value}>
                {label(value)}
              </option>
            ))}
          </select>
          <select
            aria-label="Filter service"
            value={service}
            onChange={(event) => {
              setService(event.target.value);
              setPage(1);
            }}
          >
            <option value="">All services</option>
            {['user-service', 'order-service', 'payment-service'].map((value) => (
              <option key={value}>{value}</option>
            ))}
          </select>
          <button
            className="text-button"
            onClick={() => {
              setQuery('');
              setSeverity('');
              setStatus('');
              setService('');
              setPage(1);
            }}
          >
            Reset
          </button>
        </div>
      )}
      {result.loading && <LoadingState label="Loading persisted incidents…" />}
      {result.error && <ErrorMessage message={result.error} />}
      {rows?.length ? (
        <div className="table-scroll">
          <table>
            <caption className="sr-only">
              Persisted incidents. Select an incident to inspect real event evidence.
            </caption>
            <thead>
              <tr>
                <th>Incident</th>
                <th>Severity</th>
                <th>Status</th>
                <th>Detected · UTC</th>
                <th>Occurrences</th>
                <th>Details</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((item) => (
                <tr key={item.id}>
                  <td>
                    <button className="incident-link" onClick={() => inspect(item.id)}>
                      <span className="mono muted">{item.id}</span>
                      <strong>{item.title}</strong>
                      <span className="service-name">{item.service_name}</span>
                    </button>
                  </td>
                  <td>
                    <Badge label={label(item.severity)} />
                  </td>
                  <td>
                    <Badge label={label(item.status)} />
                  </td>
                  <td className="muted mono">
                    <div>First: {timestamp(item.first_seen)}</div>
                    <div>Latest: {timestamp(item.last_seen)}</div>
                  </td>
                  <td>{item.occurrence_count}</td>
                  <td>
                    <button
                      className="icon-button"
                      aria-label={`Inspect ${item.id}`}
                      onClick={() => inspect(item.id)}
                    >
                      <ArrowUpRight size={17} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        result.data && (
          <EmptyState
            title="No matching incidents"
            description="Trigger a local service failure or adjust your filters."
          />
        )
      )}
      {!compact && result.data && (
        <div className="table-footer">
          <button disabled={page === 1} onClick={() => setPage(page - 1)}>
            Previous
          </button>
          <span>
            Page {page} · {result.data.total} persisted incidents
          </span>
          <button disabled={page * 20 >= result.data.total} onClick={() => setPage(page + 1)}>
            Next
          </button>
        </div>
      )}
      <dialog
        ref={dialog}
        aria-labelledby="incident-title"
        className="incident-dialog"
        onClose={() => setSelected(null)}
        onClick={(event) => {
          if (event.target === dialog.current) dialog.current?.close();
        }}
      >
        <div className="dialog-header">
          <span className="eyebrow">PERSISTED INCIDENT</span>
          <button
            className="icon-button"
            aria-label="Close incident details"
            onClick={() => dialog.current?.close()}
          >
            <X size={20} />
          </button>
        </div>
        {selected && <IncidentDetails key={selected} id={selected} />}
      </dialog>
    </>
  );
}

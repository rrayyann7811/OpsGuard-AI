'use client';
import { isPublicDemo } from '@/lib/runtime-mode';
import { useEffect, useRef, useState } from 'react';
import { BookOpen, Database, Search, X } from 'lucide-react';
import { label, timestamp, type Page } from '@/lib/monitoring';
import {
  searchKnowledge,
  type HistoricalIncident,
  type HistoricalMatch,
  type KnowledgeStatus,
  type SearchResponse,
} from '@/lib/knowledge';
import { usePolling } from './monitoring-provider';
import { Badge, EmptyState, ErrorMessage, LoadingState, Panel, StatCard } from './ui';

function HistoricalDetail({ id }: { id: string }) {
  const detail = usePolling<{ incident: HistoricalIncident }>(`/api/knowledge/incidents/${id}`);
  const item = detail.data?.incident;
  return (
    <>
      {detail.loading && <LoadingState label="Loading historical source…" />}
      {detail.error && <ErrorMessage message={detail.error} />}
      {item && (
        <>
          <h2>{item.title}</h2>
          <div className="dialog-badges">
            <span className="sample-tag">SYNTHETIC</span>
            <Badge label={label(item.severity)} />
            <span>{item.service_name}</span>
          </div>
          <p className="mono">
            {item.id} · {item.incident_date} · HTTP {item.http_status}
          </p>
          <h3>Symptoms</h3>
          <p>{item.symptoms}</p>
          <h3>Error evidence</h3>
          <pre>
            {item.error_type}: {item.error_message}
          </pre>
          <h3>Historical root cause</h3>
          <p>{item.root_cause}</p>
          <h3>Resolution</h3>
          <p>{item.resolution}</p>
          <h3>Runbook steps</h3>
          <ol>
            {item.runbook.map((step, index) => (
              <li key={index}>{step}</li>
            ))}
          </ol>
          <h3>Relevant code context</h3>
          <pre>{item.code_context}</pre>
          <p>Technology: {item.technology.join(', ')}</p>
          <p className="muted">
            Source: {item.source_ref} · {item.id}. Original authored synthetic record, not a real
            company postmortem.
          </p>
        </>
      )}
    </>
  );
}
export function HistoricalCards({
  items,
}: {
  items: { incident: HistoricalIncident; match?: HistoricalMatch }[];
}) {
  const [selected, setSelected] = useState<string | null>(null);
  const dialog = useRef<HTMLDialogElement>(null);
  return (
    <>
      <div className="knowledge-grid">
        {items.map(({ incident, match }) => (
          <article className="service-card knowledge-card" key={incident.id}>
            <div className="dialog-badges">
              <span className="sample-tag">SYNTHETIC</span>
              <Badge label={label(incident.severity)} />
            </div>
            <button
              className="incident-link"
              onClick={() => {
                setSelected(incident.id);
                dialog.current?.showModal();
              }}
            >
              <strong>{incident.title}</strong>
              <span className="service-name">
                {incident.service_name} · {incident.id}
              </span>
            </button>
            {match && (
              <p className="mono">
                Cosine similarity {match.similarity_score.toFixed(3)}
                {match.rank_score !== match.similarity_score &&
                  ` · Hybrid rank ${match.rank_score.toFixed(3)}`}
              </p>
            )}
            <p>
              <strong>Historical cause:</strong> {incident.root_cause}
            </p>
            <p>
              <strong>Resolution:</strong> {incident.resolution}
            </p>
            <p className="muted">Source: {incident.source_ref}</p>
            <button
              className="text-button"
              onClick={() => {
                setSelected(incident.id);
                dialog.current?.showModal();
              }}
            >
              Inspect historical incident
            </button>
          </article>
        ))}
      </div>
      <dialog
        className="incident-dialog"
        aria-label="Historical incident details"
        ref={dialog}
        onClose={() => setSelected(null)}
        onClick={(event) => {
          if (event.target === dialog.current) dialog.current?.close();
        }}
      >
        <div className="dialog-header">
          <span className="eyebrow">HISTORICAL SOURCE EVIDENCE</span>
          <button
            className="icon-button"
            aria-label="Close historical details"
            onClick={() => dialog.current?.close()}
          >
            <X size={20} />
          </button>
        </div>
        {selected && <HistoricalDetail key={selected} id={selected} />}
      </dialog>
    </>
  );
}
export function SimilarHistoricalIncidents({ incidentId }: { incidentId: string }) {
  const [result, setResult] = useState<SearchResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const controller = useRef<AbortController | null>(null);
  useEffect(() => () => controller.current?.abort(), []);
  async function search() {
    controller.current?.abort();
    const active = new AbortController();
    controller.current = active;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const data = await searchKnowledge(
        `/api/knowledge/similar/${incidentId}`,
        { top_k: 3 },
        active.signal,
      );
      if (!active.signal.aborted) setResult(data);
    } catch (failure) {
      if (!active.signal.aborted)
        setError(failure instanceof Error ? failure.message : 'Historical search failed');
    } finally {
      if (!active.signal.aborted) setLoading(false);
    }
  }
  return (
    <section className="historical-related">
      <h3>Related Historical Incidents</h3>
      <p className="muted">
        Historical matches are evidence to inspect, not the verified root cause of this incident.
        Local AI analysis requires explicit runtime setup and authorization. Live inference remains
        unverified.
      </p>
      <button className="button secondary" disabled={loading || isPublicDemo} onClick={search}>
        Find Similar Historical Incidents
      </button>
      {loading && <LoadingState label="Loading local model and searching historical evidence…" />}
      {error && <ErrorMessage message={error} />}
      {result && !result.items.length && <p>No historical matches met the similarity threshold.</p>}
      {result && (
        <HistoricalCards
          items={result.items.map((match) => ({ incident: match.incident, match }))}
        />
      )}
    </section>
  );
}
export function KnowledgePage() {
  const status = usePolling<KnowledgeStatus>('/api/knowledge/status');
  const [query, setQuery] = useState('');
  const [service, setService] = useState('');
  const [severity, setSeverity] = useState('');
  const [page, setPage] = useState(1);
  const [result, setResult] = useState<SearchResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const controller = useRef<AbortController | null>(null);
  useEffect(() => () => controller.current?.abort(), []);
  const params = new URLSearchParams({ page: String(page), page_size: '6' });
  if (service) params.set('service', service);
  if (severity) params.set('severity', severity);
  const browse = usePolling<Page<HistoricalIncident>>(`/api/knowledge/incidents?${params}`);
  async function search(event: React.FormEvent) {
    event.preventDefault();
    controller.current?.abort();
    const active = new AbortController();
    controller.current = active;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const data = await searchKnowledge(
        '/api/knowledge/search',
        {
          query: query.trim(),
          service: service || null,
          severity: severity || null,
          ranking: 'semantic',
          top_k: 3,
          min_score: 0.3,
        },
        active.signal,
      );
      if (!active.signal.aborted) setResult(data);
    } catch (failure) {
      if (!active.signal.aborted)
        setError(failure instanceof Error ? failure.message : 'Historical search failed');
    } finally {
      if (!active.signal.aborted) setLoading(false);
    }
  }
  function resetSearch() {
    controller.current?.abort();
    setResult(null);
    setLoading(false);
    setError(null);
  }
  const data = status.data;
  return (
    <>
      <div className="info-note">
        <BookOpen size={18} />
        <p>
          {isPublicDemo
            ? 'Browse bundled synthetic examples. Semantic search is disabled in this public demonstration.'
            : 'Search an attributed synthetic incident library with local embeddings.'}{' '}
          Retrieved historical causes are not verified conclusions about current incidents.
        </p>
      </div>
      {status.error && <ErrorMessage message={status.error} />}
      {data?.status === 'unavailable' && <ErrorMessage message={data.message} />}
      <div className="stats-grid three">
        <StatCard
          label="Indexed incidents"
          value={data?.indexed_incidents ?? '—'}
          detail={`${data?.indexed_chunks ?? '—'} searchable chunks · synthetic dataset`}
          icon={<BookOpen size={18} />}
        />
        <StatCard
          label="Vector collection"
          value={data?.status ?? 'Checking'}
          detail={`${data?.mode ?? 'Unknown mode'} · ${data?.collection ?? 'Not verified'}`}
          icon={<Database size={18} />}
        />
        <StatCard
          label="Knowledge sources"
          value={data?.source_count ?? '—'}
          detail={`Last indexed: ${timestamp(data?.last_indexed_at ?? null)}`}
          icon={<BookOpen size={18} />}
        />
      </div>
      <p className="muted">
        Embedding model:{' '}
        <span className="mono">{data?.embedding_model ?? 'Checking configuration'}</span> ·{' '}
        {data?.dimension ?? '—'} dimensions ·{' '}
        {isPublicDemo
          ? 'No model is loaded'
          : data?.embedding_loaded
            ? 'Loaded locally'
            : 'Loads locally on first search'}
        .
      </p>
      <Panel
        title="Search historical incidents"
        description="Questions, error messages, stack traces, or incident summaries. Scores are cosine similarity, not confidence probabilities."
      >
        <form className="knowledge-search" onSubmit={search}>
          <label className="search-input">
            <Search size={16} />
            <textarea
              aria-label="Historical incident query"
              placeholder="Describe the failure or paste safe error evidence…"
              value={query}
              minLength={3}
              maxLength={6000}
              required
              onChange={(event) => setQuery(event.target.value)}
            />
          </label>
          <div className="filter-bar">
            <select
              aria-label="Historical service filter"
              value={service}
              onChange={(event) => {
                resetSearch();
                setService(event.target.value);
                setPage(1);
              }}
            >
              <option value="">All services</option>
              {['user-service', 'order-service', 'payment-service'].map((value) => (
                <option key={value}>{value}</option>
              ))}
            </select>
            <select
              aria-label="Historical severity filter"
              value={severity}
              onChange={(event) => {
                resetSearch();
                setSeverity(event.target.value);
                setPage(1);
              }}
            >
              <option value="">All severities</option>
              {['critical', 'high', 'medium', 'low'].map((value) => (
                <option key={value}>{value}</option>
              ))}
            </select>
            <button
              className="button"
              disabled={loading || isPublicDemo || query.trim().length < 3}
              type="submit"
            >
              Search knowledge
            </button>
            <button className="text-button" type="button" onClick={resetSearch}>
              Browse library
            </button>
          </div>
        </form>
        {loading && <LoadingState label="Loading local model and searching Qdrant…" />}
        {error && <ErrorMessage message={error} />}
        {result && (
          <>
            <p className="muted">
              {result.total} matches · {result.duration_ms.toFixed(1)} ms backend retrieval ·{' '}
              {result.ranking}
            </p>
            {result.items.length ? (
              <HistoricalCards
                items={result.items.map((match) => ({ incident: match.incident, match }))}
              />
            ) : (
              <EmptyState
                title="No historical matches"
                description="No source met the threshold. Try a more specific error description or adjust filters."
              />
            )}
          </>
        )}
      </Panel>
      {!result && !loading && (
        <Panel
          title="Incident knowledge library"
          description="Indexed historical sources · clearly synthetic, never operational incident records"
        >
          {browse.loading && <LoadingState label="Loading indexed history…" />}
          {browse.error && <ErrorMessage message={browse.error} />}
          {browse.data?.items.length ? (
            <HistoricalCards items={browse.data.items.map((incident) => ({ incident }))} />
          ) : (
            browse.data && (
              <EmptyState
                title="No indexed historical incidents"
                description="Run the documented local indexing command to populate Qdrant."
              />
            )
          )}
          {browse.data && (
            <div className="table-footer">
              <button disabled={page === 1} onClick={() => setPage(page - 1)}>
                Previous sources
              </button>
              <span>
                Page {page} · {browse.data.total} historical incidents
              </span>
              <button disabled={page * 6 >= browse.data.total} onClick={() => setPage(page + 1)}>
                Next sources
              </button>
            </div>
          )}
        </Panel>
      )}
    </>
  );
}

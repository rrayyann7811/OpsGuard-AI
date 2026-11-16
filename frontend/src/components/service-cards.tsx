'use client';
import { isHostedApi } from '@/lib/runtime-mode';
import Link from 'next/link';
import { useState } from 'react';
import { Box, Search } from 'lucide-react';
import { timestamp } from '@/lib/monitoring';
import { useMonitoring } from './monitoring-provider';
import { Badge, EmptyState, ErrorMessage, LoadingState } from './ui';
export function ServiceCards({ compact = false }: { compact?: boolean }) {
  const [query, setQuery] = useState('');
  const [status, setStatus] = useState('');
  const { services } = useMonitoring();
  const rows = services.data?.items.filter(
    (item) =>
      item.service_name.includes(query.toLowerCase().trim()) && (!status || status === item.status),
  );
  return (
    <>
      {!compact && (
        <div className="filter-bar">
          <label className="search-input">
            <Search size={16} />
            <input
              aria-label="Search services"
              placeholder="Search services…"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
            />
          </label>
          <select
            aria-label="Filter service health"
            value={status}
            onChange={(event) => setStatus(event.target.value)}
          >
            <option value="">All health states</option>
            {['Healthy', 'Degraded', 'Unavailable', 'Unknown'].map((value) => (
              <option key={value}>{value}</option>
            ))}
          </select>
        </div>
      )}
      {services.loading && <LoadingState label="Loading service health…" />}
      {services.error && <ErrorMessage message={services.error} />}
      <div className={compact ? 'service-list' : 'service-grid'}>
        {rows?.map((item) => (
          <article className="service-card" key={item.service_name}>
            <div className="service-top">
              <span className={`service-icon ${item.status.toLowerCase()}`}>
                <Box size={18} />
              </span>
              <div>
                <h3>{item.service_name}</h3>
                <p>
                  {item.available === null
                    ? isHostedApi
                      ? 'Monitoring not configured'
                      : 'Awaiting first check'
                    : item.available
                      ? 'Health endpoint responding'
                      : 'Health endpoint unavailable'}
                </p>
              </div>
              <Badge label={item.status} />
            </div>
            <div className="service-metrics">
              <span>
                Latency<strong>{item.latency_ms === null ? '—' : `${item.latency_ms} ms`}</strong>
              </span>
              <span>
                Consecutive failures<strong>{item.consecutive_failures}</strong>
              </span>
            </div>
            {!compact && (
              <div className="service-metrics">
                <span>
                  Active incidents<strong>{item.incident_summary?.active ?? '—'}</strong>
                </span>
                <span>
                  Recorded incidents<strong>{item.incident_summary?.total ?? '—'}</strong>
                </span>
              </div>
            )}
            {!compact && (
              <Link
                className="text-link"
                href={`/incidents?service=${encodeURIComponent(item.service_name)}`}
              >
                View service incidents
              </Link>
            )}
            <p>Last attempt: {timestamp(item.last_attempt)}</p>
            {!compact && <p>Last success: {timestamp(item.last_success)}</p>}
            {item.failure_reason && <p className="muted">{item.failure_reason}</p>}
          </article>
        ))}
      </div>
      {rows && !rows.length && (
        <EmptyState title="No services found" description="Adjust your search or health filter." />
      )}
    </>
  );
}

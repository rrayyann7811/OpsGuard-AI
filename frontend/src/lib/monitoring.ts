import { publicDemoData } from './public-demo';
import { isPublicDemo } from './runtime-mode';
import { apiUrl } from './health';
export type Incident = {
  id: string;
  service_name: string;
  title: string;
  severity: string;
  status: 'OPEN' | 'INVESTIGATING' | 'RESOLVED';
  error_signature: string;
  error_type: string;
  error_message: string;
  stack_trace: string | null;
  endpoint: string;
  http_status: number;
  first_seen: string;
  last_seen: string;
  occurrence_count: number;
  created_at: string;
  updated_at: string;
};
export type IncidentEvent = {
  event_id: string;
  timestamp: string;
  request_id: string;
  error_type: string;
  error_message: string;
  stack_trace: string | null;
  http_status: number;
  duration_ms: number;
  endpoint: string;
};
export type Page<T> = { items: T[]; total: number; page: number; page_size: number };
export type ServiceHealth = {
  service_name: string;
  status: 'Healthy' | 'Degraded' | 'Unavailable' | 'Unknown';
  available: boolean | null;
  last_success: string | null;
  last_attempt: string | null;
  latency_ms: number | null;
  failure_reason: string | null;
  consecutive_failures: number;
  incident_summary?: { total: number; active: number; resolved: number };
};
export type Summary = {
  active: number;
  critical: number;
  resolved: number;
  total: number;
  by_severity: Record<string, number>;
  history: { date: string; events: number }[];
};
export const label = (text: string) => text[0]?.toUpperCase() + text.slice(1).toLowerCase();
export const timestamp = (text: string | null) =>
  text ? new Date(text).toISOString().slice(0, 19).replace('T', ' ') + ' UTC' : 'Not checked';
export function incidentPath(filters: {
  query: string;
  severity: string;
  status: string;
  service: string;
  page: number;
}) {
  const params = new URLSearchParams({ page: String(filters.page), page_size: '20' });
  if (filters.query.trim()) params.set('search', filters.query.trim());
  if (filters.severity) params.set('severity', filters.severity);
  if (filters.status) params.set('status', filters.status);
  if (filters.service) params.set('service', filters.service);
  return `/api/incidents?${params}`;
}
export async function getData<T>(path: string, signal: AbortSignal): Promise<T> {
  if (isPublicDemo) return structuredClone(publicDemoData(path)) as T;
  const response = await fetch(apiUrl + path, {
    signal: AbortSignal.any([signal, AbortSignal.timeout(4000)]),
    cache: 'no-store',
  });
  if (!response.ok) throw new Error(`Monitoring API returned HTTP ${response.status}`);
  const data = await response.json();
  if (!data || typeof data !== 'object') throw new Error('Invalid monitoring response');
  return data as T;
}

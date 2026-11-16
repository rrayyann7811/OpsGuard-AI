import { isPublicDemo, isHostedApi } from './runtime-mode';
import { apiUrl } from './health';
export type HistoricalIncident = {
  id: string;
  title: string;
  service_name: string;
  symptoms: string;
  error_type: string;
  error_message: string;
  root_cause: string;
  resolution: string;
  technology: string[];
  severity: string;
  incident_date: string;
  source_ref: string;
  runbook: string[];
  code_context: string;
  http_status: number;
  synthetic: true;
};
export type KnowledgeStatus = {
  status: 'ready' | 'empty' | 'unavailable';
  mode: string;
  collection: string;
  indexed_incidents: number | null;
  indexed_chunks: number | null;
  source_count: number | null;
  last_indexed_at: string | null;
  embedding_model: string;
  dimension: number;
  embedding_loaded: boolean;
  message: string;
};
export type HistoricalMatch = {
  incident: HistoricalIncident;
  similarity_score: number;
  rank_score: number;
  matched_chunk: string;
  source_ref: string;
  ranking_signals: string[];
};
export type SearchResponse = {
  items: HistoricalMatch[];
  total: number;
  ranking: string;
  duration_ms: number;
  notice: string;
};
export async function searchKnowledge(
  path: string,
  body: object,
  signal: AbortSignal,
): Promise<SearchResponse> {
  if (isPublicDemo || isHostedApi)
    throw new Error('Semantic search is local-only. Browse the bundled synthetic examples.');
  const response = await fetch(apiUrl + path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    cache: 'no-store',
    signal: AbortSignal.any([signal, AbortSignal.timeout(60000)]),
  });
  if (!response.ok)
    throw new Error(
      response.status === 422
        ? 'Check your search query and filters.'
        : 'Historical retrieval is unavailable. Check the knowledge index and local model configuration.',
    );
  const data = await response.json();
  if (!data || !Array.isArray(data.items)) throw new Error('Unexpected retrieval response');
  return data;
}

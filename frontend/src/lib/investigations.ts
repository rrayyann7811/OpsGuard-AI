import { isPublicDemo } from './runtime-mode';
import { apiUrl } from './health';
export type AgentConfiguration = {
  available: boolean;
  mode: string;
  message: string;
  read_only: boolean;
  backend?: string;
  model?: string;
  paid_authorization_required?: boolean;
};
export type InvestigationEvidence = {
  id: string;
  kind: 'log' | 'source' | 'historical' | 'git';
  content: string;
  path?: string;
  start_line?: number;
  end_line?: number;
  commit_sha?: string;
  operation?: string;
  historical_id?: string;
  similarity_score?: number;
  source_ref?: string;
};
export type Finding = { classification: string; statement: string; evidence_ids: string[] };
export type InvestigationReport = {
  suspected_root_cause: Finding;
  error_summary: string;
  verified_facts: Finding[];
  explanation: Finding[];
  affected_files: { path: string; start_line: number; end_line: number; evidence_id: string }[];
  suspected_commits: { commit_sha: string; explanation: string; evidence_id: string }[];
  recommended_remediation: Finding[];
  limitations: string[];
  confidence: { category: string; reason: string };
  historical_references: {
    historical_id: string;
    evidence_id: string;
    similarity_score: number;
    source_ref: string;
  }[];
  execution_mode: string;
};
export type Investigation = {
  id: string;
  incident_id: string;
  service_name: string;
  status: string;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  duration_ms: number | null;
  error_message: string | null;
  error_code: string | null;
  root_cause_summary: string | null;
  execution_metadata: {
    mode?: string;
    provider?: string;
    model?: string;
    backend?: string;
    metrics?: { prompt_bytes?: number; output_bytes?: number; inference_ms?: number };
  };
  evidence?: InvestigationEvidence[];
  report?: InvestigationReport | null;
};
export type InvestigationSummary = {
  total: number;
  completed: number;
  running: number;
  failed: number;
  cancelled: number;
  average_duration_ms: number | null;
};
export async function investigationAction(
  path: string,
  token: string,
  body: object,
  signal: AbortSignal,
) {
  if (isPublicDemo)
    throw new Error('Investigation actions are disabled in the public demonstration.');
  const response = await fetch(apiUrl + path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
    body: JSON.stringify(body),
    signal: AbortSignal.any([signal, AbortSignal.timeout(12000)]),
    cache: 'no-store',
  });
  if (!response.ok)
    throw new Error(
      response.status === 401
        ? 'Agent authentication failed. Check the dedicated local agent token.'
        : response.status === 409
          ? 'An investigation is already active or the action conflicts with its state.'
          : response.status === 503
            ? 'The selected AI backend is unavailable or its configuration checks failed. No simulated analysis is substituted.'
            : `Investigation action failed (HTTP ${response.status}).`,
    );
  return (await response.json()) as { investigation: Investigation };
}

export function executionLabel(mode: string | undefined): string {
  if (mode === 'local-ollama') return 'Local AI Investigation';
  if (mode === 'test-double') return 'TEST DOUBLE — NOT CODEX';
  if (mode === 'live-codex') return 'LOCAL CODEX';
  if (mode === 'live-managed-codex') return 'MANAGED CODEX';
  return 'EXECUTION UNVERIFIED';
}

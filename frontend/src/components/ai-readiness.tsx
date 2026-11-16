'use client';
import { isPublicDemo } from '@/lib/runtime-mode';
import { useEffect, useState } from 'react';
import { RefreshCw } from 'lucide-react';
import { getData, timestamp } from '@/lib/monitoring';
import { ErrorMessage, LoadingState, Panel } from './ui';

export type AIReadiness = {
  backend: string;
  model?: string;
  model_configured: boolean;
  execution_enabled?: boolean;
  action_token_configured?: boolean;
  server_reachable?: boolean;
  model_installed?: boolean | null;
  memory_guard: string;
  memory?: {
    available_estimate_bytes: number | null;
    required_estimate_bytes: number;
    method: string;
  } | null;
  live_inference_verified: boolean;
  verification_status: string;
  diagnostic_mode?: string;
  checked_at?: string;
  error_code?: string | null;
  stop_unconfirmed?: boolean;
};
const advice: Record<string, string> = {
  OLLAMA_UNAVAILABLE:
    'Ollama did not respond. Start the existing runtime manually on loopback when you are ready to test; this website never starts it.',
  OLLAMA_LOCAL_MODEL_UNAVAILABLE:
    'Select the exact installed local model name in AGENT_OLLAMA_MODEL. The intended model is llama3.2:3b; no model is downloaded automatically.',
  OLLAMA_MEMORY_INSUFFICIENT:
    'Memory admission is blocked. Close unneeded applications yourself and check again later. Do not lower the memory guard.',
  OLLAMA_MODEL_TOO_LARGE:
    'The selected model exceeds the local size limit. Use the existing lightweight llama3.2:3b model when resources permit.',
  OLLAMA_OTHER_MODEL_LOADED:
    'Another model is loaded. Finish that session before this investigation; OpsGuard does not stop unrelated sessions.',
  LOCAL_BACKEND_NOT_SELECTED:
    'Set AGENT_EXECUTION_BACKEND=local-ollama in the backend environment and restart FastAPI. Managed execution should remain disabled.',
};
const gib = (bytes: number | null | undefined) =>
  bytes == null ? 'Unknown' : `${(bytes / 1024 ** 3).toFixed(2)} GiB`;

export function AIReadinessPanel() {
  return isPublicDemo ? (
    <Panel title="AI execution disabled" description="Public demonstration">
      <p className="readiness-body">
        No model, credentials or inference runtime is connected. No AI diagnosis is generated. Real
        local inference verification remains pending.
      </p>
    </Panel>
  ) : (
    <LocalAIReadinessPanel />
  );
}
function LocalAIReadinessPanel() {
  const [revision, setRevision] = useState(0);
  const [state, setState] = useState<{
    data: AIReadiness | null;
    error: string | null;
    loading: boolean;
  }>({ data: null, error: null, loading: true });
  useEffect(() => {
    const controller = new AbortController();
    getData<AIReadiness>('/api/investigations/readiness', controller.signal)
      .then((data) => {
        if (!controller.signal.aborted) setState({ data, error: null, loading: false });
      })
      .catch(() => {
        if (!controller.signal.aborted)
          setState({
            data: null,
            error: 'AI readiness could not be checked. Verify the backend connection and retry.',
            loading: false,
          });
      });
    return () => controller.abort();
  }, [revision]);
  const data = state.data;
  return (
    <Panel
      title="Local AI readiness"
      description="Read-only checks. No model is loaded and no inference is started."
      className="ai-readiness-panel"
    >
      <div className="readiness-body">
        <div className="info-note">
          <p>
            <strong>Real inference verification pending.</strong> Configuring a model or passing
            preflight does not verify a diagnosis. Website testing works with AI disabled.
          </p>
        </div>
        {state.loading && <LoadingState label="Checking local AI readiness…" />}
        {state.error && <ErrorMessage message={state.error} />}
        {data && (
          <>
            {data.diagnostic_mode === 'test-double' && (
              <p className="sample-tag">TEST DOUBLE — diagnostic fixture only</p>
            )}
            <dl className="readiness-grid">
              <div>
                <dt>Execution backend</dt>
                <dd>{data.backend}</dd>
              </div>
              <div>
                <dt>Selected model</dt>
                <dd>{data.model_configured ? data.model : 'Not selected'}</dd>
              </div>
              <div>
                <dt>Model configuration</dt>
                <dd>
                  {data.model_configured
                    ? 'Configured; not inference verified'
                    : 'Set AGENT_OLLAMA_MODEL explicitly'}
                </dd>
              </div>
              <div>
                <dt>Execution authorization</dt>
                <dd>
                  {data.execution_enabled
                    ? 'Enabled; each run still requires authorization'
                    : 'Disabled — safe for website testing'}
                </dd>
              </div>
              <div>
                <dt>Local action token</dt>
                <dd>
                  {data.action_token_configured ? 'Configured; value hidden' : 'Not configured'}
                </dd>
              </div>
              <div>
                <dt>Ollama connection</dt>
                <dd>
                  {data.server_reachable === true
                    ? 'Reachable on loopback'
                    : data.server_reachable === false
                      ? 'Unavailable'
                      : 'Not checked'}
                </dd>
              </div>
              <div>
                <dt>Required model installed</dt>
                <dd>
                  {data.model_installed === true
                    ? 'Verified by read-only inventory'
                    : data.model_installed === false
                      ? 'Not found for this configuration'
                      : 'Not checked'}
                </dd>
              </div>
              <div>
                <dt>Memory guard</dt>
                <dd>
                  {data.memory_guard === 'passed'
                    ? 'Passed at this check only'
                    : data.memory_guard === 'blocked'
                      ? 'Blocked — insufficient estimated headroom'
                      : 'Not checked'}
                </dd>
              </div>
              <div>
                <dt>Last inference verification</dt>
                <dd>Pending — no successful live verification recorded</dd>
              </div>
              <div>
                <dt>Readiness checked</dt>
                <dd>{data.checked_at ? timestamp(data.checked_at) : 'Not checked'}</dd>
              </div>
            </dl>
            {data.memory && (
              <p className="field-help">
                Available estimate: {gib(data.memory.available_estimate_bytes)} · Required estimate:{' '}
                {gib(data.memory.required_estimate_bytes)}. Reclaimable memory is not reserved RAM.
                The guard runs again before inference.
              </p>
            )}
            {data.stop_unconfirmed && (
              <ErrorMessage message="A prior generation stop is unconfirmed. Review the runtime and reconcile it before another run." />
            )}
            {data.error_code && (
              <p className="readiness-help">
                {advice[data.error_code] ??
                  'The runtime returned an unsupported response or timed out. Check Ollama locally; no inference was attempted by this check.'}
              </p>
            )}
          </>
        )}
        <button
          className="button secondary"
          disabled={state.loading}
          onClick={() => {
            setState((previous) => ({ ...previous, loading: true, error: null }));
            setRevision((value) => value + 1);
          }}
        >
          <RefreshCw size={15} />
          Check AI readiness
        </button>
        <details className="investigation-evidence">
          <summary>Local setup reference</summary>
          <p className="field-help">
            Use the existing llama3.2:3b model. Configure these backend-only values, keep execution
            disabled for website testing, and restart FastAPI after an intentional configuration
            change. No API key is needed.
          </p>
          <pre>{`AGENT_EXECUTION_BACKEND=local-ollama
AGENT_OLLAMA_MODEL=llama3.2:3b
AGENT_EXECUTION_ENABLED=false
AGENT_MANAGED_ENABLED=false
AGENT_MANAGED_HTTP_ENABLED=false`}</pre>
        </details>
        <p className="field-help">
          Configuration is server-side: AGENT_EXECUTION_BACKEND, AGENT_OLLAMA_URL and
          AGENT_OLLAMA_MODEL. Keep AGENT_EXECUTION_ENABLED=false until manual AI testing. Never put
          tokens in NEXT_PUBLIC variables.
        </p>
      </div>
    </Panel>
  );
}

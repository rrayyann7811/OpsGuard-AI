'use client';
import { isPublicDemo, isHostedApi } from '@/lib/runtime-mode';
import { createContext, useContext, useEffect, useState } from 'react';
import { getData, type Summary, type ServiceHealth } from '@/lib/monitoring';
import { ErrorMessage, LoadingState } from './ui';

export function usePolling<T>(path: string | null) {
  const [state, setState] = useState<{ key: string | null; data: T | null; error: string | null }>({
    key: null,
    data: null,
    error: null,
  });
  useEffect(() => {
    if (!path) return;
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    async function poll() {
      let failed = false;
      try {
        const data = await getData<T>(path!, controller.signal);
        if (!controller.signal.aborted) setState({ key: path, data, error: null });
      } catch {
        failed = true;
        if (!controller.signal.aborted)
          setState((previous) => ({
            key: path,
            data: previous.key === path ? previous.data : null,
            error: 'Monitoring backend is offline or unavailable. Retrying automatically.',
          }));
      }
      if (!controller.signal.aborted && !isPublicDemo)
        timer = setTimeout(poll, failed ? 10000 : 5000);
    }
    void poll();
    return () => {
      controller.abort();
      clearTimeout(timer);
    };
  }, [path]);
  return state.key === path
    ? { ...state, loading: !state.data && !state.error }
    : { data: null, error: null, loading: Boolean(path) };
}
function useMonitoringState() {
  return {
    summary: usePolling<Summary>('/api/incidents/summary'),
    services: usePolling<{ items: ServiceHealth[] }>('/api/services'),
  };
}
const Context = createContext<ReturnType<typeof useMonitoringState> | null>(null);
export function MonitoringProvider({ children }: { children: React.ReactNode }) {
  const state = useMonitoringState();
  return <Context.Provider value={state}>{children}</Context.Provider>;
}
export function useMonitoring() {
  const context = useContext(Context);
  if (!context) throw new Error('MonitoringProvider is required');
  return context;
}
export function MonitoringNotice() {
  const { summary, services } = useMonitoring();
  if (isPublicDemo) return null;
  if (summary.error || services.error)
    return (
      <ErrorMessage message="Live monitoring disconnected. Previously loaded records may be stale; retrying automatically." />
    );
  if (summary.loading || services.loading)
    return <LoadingState label="Connecting live incident monitoring…" />;
  if (isHostedApi)
    return (
      <div className="info-note">
        <p>
          Connected to the configured read-only API. Microservices are not deployed; no live health
          checks or incident persistence are configured.
        </p>
      </div>
    );
  return (
    <div className="demo-banner">
      <p>
        <strong>Live local monitoring</strong>
        <span>
          Persisted incident evidence · service checks every 10 seconds by default · dashboard
          updates every 5 seconds. Controlled simulations appear as stored incidents. Local AI is
          optional and its live verification remains pending.
        </span>
      </p>
      <span className="sample-tag">LIVE API</span>
    </div>
  );
}

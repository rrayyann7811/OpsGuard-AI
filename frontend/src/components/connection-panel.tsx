'use client';
import { isPublicDemo } from '@/lib/runtime-mode';
import { RefreshCw, ShieldCheck } from 'lucide-react';
import { useHealth } from './health-provider';
import { Panel } from './ui';

export function ConnectionPanel() {
  return isPublicDemo ? (
    <Panel title="Public demonstration" description="No backend connection">
      <div className="connection-body">
        <p>
          Bundled synthetic records illustrate the interface. Live monitoring, SQLite, Qdrant and
          Ollama require the local full-stack application.
        </p>
      </div>
    </Panel>
  ) : (
    <LocalConnectionPanel />
  );
}
function LocalConnectionPanel() {
  const { health, loading, error, refresh, checkedAt } = useHealth();
  return (
    <Panel title="Platform connection" description="Live FastAPI health check">
      <div className="connection-body">
        <div className={`connection-symbol ${health ? 'connected' : ''}`}>
          <ShieldCheck size={28} />
        </div>
        <h3>
          {loading ? 'Checking backend' : health ? 'Backend is connected' : 'Backend is offline'}
        </h3>
        <p>
          {health
            ? 'API and SQLite are responding. Service availability is shown separately by real health polling.'
            : 'Start the FastAPI server to connect your local workspace.'}
        </p>
        <div className="connection-row">
          <span>API service</span>
          <span>{loading ? 'Checking…' : health ? 'Connected' : 'Unavailable'}</span>
        </div>
        <div className="connection-row">
          <span>SQLite database</span>
          <span>{health ? 'Connected' : 'Not verified'}</span>
        </div>
        <div className="connection-row">
          <span>Last checked</span>
          <span>{checkedAt ?? 'Pending'}</span>
        </div>
        {error && <p className="connection-error">{error}</p>}
        <button className="button secondary full-width" disabled={loading} onClick={refresh}>
          <RefreshCw size={15} className={loading ? 'spin' : ''} />
          Check connection
        </button>
      </div>
    </Panel>
  );
}

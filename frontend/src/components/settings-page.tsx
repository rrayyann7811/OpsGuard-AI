'use client';
import { isPublicDemo } from '@/lib/runtime-mode';
import { ArrowRight, Check, CircleCheck, RefreshCw } from 'lucide-react';
import { useState } from 'react';
import { ConnectionPanel } from './connection-panel';
import { AIReadinessPanel } from './ai-readiness';
import { apiUrl } from '@/lib/health';
import { useHealth } from './health-provider';
import { preferenceKey, usePreferences } from './preferences';
import { ErrorMessage, LoadingState, Panel } from './ui';

export function SettingsPage() {
  const { health, loading, error, refresh } = useHealth();
  const { name, compact } = usePreferences();
  const [feedback, setFeedback] = useState('');
  function save(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const fields = new FormData(event.currentTarget);
    const preferences = {
      name: String(fields.get('name') ?? '').trim(),
      compact: fields.get('compact') === 'on',
    };
    try {
      localStorage.setItem(preferenceKey, JSON.stringify(preferences));
      window.dispatchEvent(new Event('opsguard:preferences'));
      setFeedback('Preferences saved on this browser.');
    } catch {
      setFeedback('Preferences could not be saved. Browser storage may be unavailable.');
    }
  }
  return (
    <div className="settings-grid">
      <AIReadinessPanel />
      <Panel title="Workspace preferences" description="Saved locally in this browser">
        <form
          className="settings-form"
          onSubmit={save}
          key={`${name}-${compact}`}
          onChange={() => setFeedback('')}
        >
          <label htmlFor="workspace-name">Workspace name</label>
          <input
            id="workspace-name"
            name="name"
            defaultValue={name}
            maxLength={60}
            required
            pattern=".*\S.*"
          />
          <p className="field-help">
            Displayed in the workspace footer. This is a local preference.
          </p>
          <label className="checkbox-label">
            <input type="checkbox" name="compact" defaultChecked={compact} />
            <span>
              Compact table rows<small>Show incident tables with less vertical spacing.</small>
            </span>
          </label>
          <button className="button primary" type="submit">
            <Check size={16} />
            Save preferences
          </button>
          <p className="save-feedback" role="status">
            {feedback}
          </p>
        </form>
      </Panel>
      {isPublicDemo ? (
        <ConnectionPanel />
      ) : (
        <Panel title="Backend connection" description="Environment configuration">
          <div className="settings-form">
            <label>API base URL</label>
            <code className="endpoint">{apiUrl}</code>
            <p className="field-help">
              Set NEXT_PUBLIC_API_URL in frontend/.env.local and restart Next.js to change this
              address.
            </p>
            {loading ? (
              <LoadingState />
            ) : error ? (
              <ErrorMessage message={error} />
            ) : (
              <div className="success-state">
                <CircleCheck size={18} />
                {health?.service} · v{health?.version} · {health?.environment}
              </div>
            )}
            <button className="button secondary" onClick={refresh} disabled={loading}>
              <RefreshCw size={15} />
              Test connection
            </button>
            <a className="text-link" href={`${apiUrl}/docs`} target="_blank" rel="noreferrer">
              Open interactive API docs <ArrowRight size={15} />
            </a>
          </div>
        </Panel>
      )}
    </div>
  );
}

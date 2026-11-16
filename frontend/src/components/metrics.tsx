'use client';
import { Activity, CircleCheck, Siren } from 'lucide-react';
import { useMonitoring } from './monitoring-provider';
import { StatCard } from './ui';
export function Metrics() {
  const { summary, services } = useMonitoring();
  const data = summary.data;
  const healthy = services.data?.items.filter((item) => item.status === 'Healthy').length;
  return (
    <div className="stats-grid">
      <StatCard
        label="Active incidents"
        value={data?.active ?? '—'}
        detail="Open and investigating"
        icon={<Siren size={18} />}
      />
      <StatCard
        label="Critical incidents"
        value={data?.critical ?? '—'}
        detail="Active critical incidents"
        icon={<Siren size={18} />}
      />
      <StatCard
        label="Healthy services"
        value={healthy === undefined ? '—' : `${healthy} / ${services.data?.items.length}`}
        detail="Observed health; no uptime estimate"
        icon={<Activity size={18} />}
      />
      <StatCard
        label="Resolved incidents"
        value={data?.resolved ?? '—'}
        detail={`${data?.total ?? '—'} persisted incidents total`}
        icon={<CircleCheck size={18} />}
      />
    </div>
  );
}

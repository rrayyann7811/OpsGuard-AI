'use client';
import { useState } from 'react';
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { useMonitoring } from './monitoring-provider';
import { EmptyState, Panel } from './ui';
const tooltipStyle = {
  background: '#172131',
  border: '1px solid #354154',
  borderRadius: 8,
  color: '#e6edf6',
};
function IncidentChart({
  data,
  field,
  name,
}: {
  data: Record<string, string | number>[];
  field: string;
  name: string;
}) {
  return (
    <div className="chart" role="img" aria-label={name}>
      <ResponsiveContainer width="100%" height="100%" minWidth={0}>
        <BarChart data={data} margin={{ left: -20, top: 20, right: 20 }}>
          <CartesianGrid vertical={false} stroke="#253041" />
          <XAxis dataKey={field} stroke="#8694aa" fontSize={11} tickLine={false} axisLine={false} />
          <YAxis
            allowDecimals={false}
            stroke="#8694aa"
            fontSize={12}
            tickLine={false}
            axisLine={false}
          />
          <Tooltip contentStyle={tooltipStyle} />
          <Bar
            dataKey="count"
            fill="#6799f6"
            radius={[4, 4, 0, 0]}
            maxBarSize={55}
            isAnimationActive={false}
          />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
export function TrafficChart() {
  const { summary } = useMonitoring();
  const [days, setDays] = useState('7');
  const history = summary.data?.history.slice(-Number(days)) ?? [];
  return (
    <Panel
      title="Incident event history"
      description="Stored event counts per UTC day; latest recorded days"
      action={
        <select
          aria-label="Chart history range"
          value={days}
          onChange={(event) => setDays(event.target.value)}
        >
          <option value="7">Latest 7 days with events</option>
          <option value="30">Latest 30 days with events</option>
        </select>
      }
    >
      {history.length ? (
        <IncidentChart
          data={history.map((item) => ({ date: item.date, count: item.events }))}
          field="date"
          name={`Persisted incident events: ${history.map((item) => `${item.date}: ${item.events}`).join(', ')}`}
        />
      ) : (
        <EmptyState
          title="No incident history yet"
          description="Charts populate when real events are persisted."
        />
      )}
    </Panel>
  );
}
export function SeverityChart() {
  const { summary } = useMonitoring();
  const data = Object.entries(summary.data?.by_severity ?? {}).map(([severity, count]) => ({
    severity,
    count,
  }));
  return (
    <Panel
      title="Incidents by severity"
      description="All persisted incidents, including resolved incidents"
    >
      {data.some((item) => item.count > 0) ? (
        <IncidentChart
          data={data}
          field="severity"
          name={`Persisted incidents by severity: ${data.map((item) => `${item.severity}: ${item.count}`).join(', ')}`}
        />
      ) : (
        <EmptyState
          title="No incidents yet"
          description="Severity counts populate from persisted incidents."
        />
      )}
    </Panel>
  );
}

export function ServiceIncidentSummary() {
  const { services } = useMonitoring();
  return (
    <Panel
      title="Incidents by service"
      description="Persisted incidents; failed health checks alone do not create incident records"
    >
      <div className="table-scroll">
        <table>
          <caption className="sr-only">Stored incident totals by monitored service</caption>
          <thead>
            <tr>
              <th>Service</th>
              <th>Active</th>
              <th>Resolved</th>
              <th>Total</th>
            </tr>
          </thead>
          <tbody>
            {services.data?.items.map((item) => (
              <tr key={item.service_name}>
                <td>{item.service_name}</td>
                <td>{item.incident_summary?.active ?? '—'}</td>
                <td>{item.incident_summary?.resolved ?? '—'}</td>
                <td>{item.incident_summary?.total ?? '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Panel>
  );
}

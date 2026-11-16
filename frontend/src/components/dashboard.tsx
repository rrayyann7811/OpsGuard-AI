'use client';
import { isPublicDemo } from '@/lib/runtime-mode';
import { InvestigationSummaryPanel } from './investigation-summary';
import { InvestigationsPage } from './investigations-page';
import { KnowledgePage } from './knowledge-page';
import { MonitoringNotice } from './monitoring-provider';
import { Metrics } from './metrics';
import { ConnectionPanel } from './connection-panel';
import { SettingsPage } from './settings-page';
import Link from 'next/link';
import { ArrowRight, Clock3, Workflow } from 'lucide-react';
import { navigation } from '@/lib/demo';
import { TrafficChart, SeverityChart, ServiceIncidentSummary } from './charts';
import { IncidentTable } from './incident-table';
import { ServiceCards } from './service-cards';
import { Panel } from './ui';
function PageTitle({ slug }: { slug: string }) {
  const page = navigation.find((item) => item.slug === slug) ?? navigation[0];
  return (
    <div className="page-title">
      <div>
        <div className="eyebrow">
          OPERATIONS WORKSPACE <span>/</span> {slug ? 'EXPLORE' : 'COMMAND CENTER'}
        </div>
        <h1>{page.label === 'Overview' ? 'Operations overview' : page.label}</h1>
        <p>{page.description}</p>
      </div>
      <span className="date-label">
        <span className="status-dot" />
        {isPublicDemo
          ? 'Synthetic demonstration · No live operations'
          : 'Local workspace · Read-only investigations'}
      </span>
    </div>
  );
}
function Overview() {
  return (
    <>
      <Metrics />
      <div className="overview-charts">
        <TrafficChart />
        <ConnectionPanel />
      </div>
      <div className="overview-lower">
        <Panel
          title="Recent incidents"
          description="Persisted incidents ordered by most recent occurrence"
          action={
            <Link className="text-link" href="/incidents">
              View all <ArrowRight size={15} />
            </Link>
          }
        >
          <IncidentTable compact />
        </Panel>
        <Panel
          title="Service health"
          description="Observed microservice availability"
          action={
            <Link className="icon-button" aria-label="View all services" href="/services">
              <ArrowRight size={17} />
            </Link>
          }
        >
          <ServiceCards compact />
        </Panel>
      </div>
      <div className="analytics-grid">
        <SeverityChart />
        <InvestigationSummaryPanel />
      </div>
      <div className="foundation-strip">
        <span className="foundation-icon">
          <Workflow size={22} />
        </span>
        <div>
          <h3>From signal to understanding</h3>
          <p>Incident evidence → historical context → local analysis → human review</p>
        </div>
        <Link className="text-link" href="/settings">
          Local AI setup
        </Link>
      </div>
    </>
  );
}
export function Dashboard({ slug = '' }: { slug?: string }) {
  return (
    <>
      <PageTitle slug={slug} />
      {slug !== 'settings' && <MonitoringNotice />}
      {slug === '' && <Overview />}
      {slug === 'incidents' && (
        <>
          <Panel title="All incidents" description="Search and inspect persisted incident evidence">
            <IncidentTable />
          </Panel>
        </>
      )}
      {slug === 'services' && (
        <Panel
          title="Service directory"
          description="Three monitored Express microservices · backend health polling"
        >
          <ServiceCards />
        </Panel>
      )}
      {slug === 'investigations' && <InvestigationsPage />}
      {slug === 'knowledge' && <KnowledgePage />}
      {slug === 'analytics' && (
        <>
          <Metrics />
          <div className="analytics-grid">
            <TrafficChart />
            <SeverityChart />
          </div>
          <InvestigationSummaryPanel />
          <ServiceIncidentSummary />
          <div className="info-note">
            <Clock3 size={18} />
            <p>
              Charts show stored incident events and incident severity. Request volume, error rates,
              and uptime are not collected.
            </p>
          </div>
        </>
      )}
      {slug === 'settings' && <SettingsPage />}
    </>
  );
}

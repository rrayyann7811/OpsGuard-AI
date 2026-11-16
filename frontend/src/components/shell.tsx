'use client';
import { isPublicDemo, isHostedApi } from '@/lib/runtime-mode';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  BookOpen,
  Boxes,
  ChartNoAxesCombined,
  FlaskConical,
  LayoutDashboard,
  Settings,
  Siren,
  X,
} from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { navigation } from '@/lib/demo';
import { MonitoringProvider, useMonitoring } from './monitoring-provider';
import { HealthProvider } from './health-provider';
import { Header } from './header';
import { Sidebar } from './sidebar';
import { WorkspaceFooter } from './preferences';
const icons = [
  LayoutDashboard,
  Siren,
  Boxes,
  FlaskConical,
  BookOpen,
  ChartNoAxesCombined,
  Settings,
];
function WorkspaceShell({ children }: { children: React.ReactNode }) {
  const path = usePathname();
  const { summary } = useMonitoring();
  const [collapsed, setCollapsed] = useState(false);
  const menu = useRef<HTMLDialogElement>(null);
  const current = navigation.find((item) => `/${item.slug}` === path) ?? navigation[0];
  useEffect(() => {
    menu.current?.close();
  }, [path]);
  const navLinks = (
    <>
      {navigation.map((item, index) => {
        const Icon = icons[index];
        return (
          <Link
            key={item.slug}
            href={`/${item.slug}`}
            className={`nav-link ${path === `/${item.slug}` ? 'active' : ''}`}
            aria-current={path === `/${item.slug}` ? 'page' : undefined}
            title={collapsed ? item.label : undefined}
            aria-label={item.label}
          >
            <Icon size={19} />
            <span>{item.label}</span>
            {item.slug === 'incidents' && (
              <span
                className="nav-count"
                aria-label={`${summary.data?.active ?? 0} active incidents`}
              >
                {summary.data?.active ?? '—'}
              </span>
            )}
          </Link>
        );
      })}
    </>
  );
  return (
    <div className={`app-shell ${collapsed ? 'collapsed' : ''}`}>
      <a className="skip-link" href="#main-content">
        Skip to content
      </a>
      <Sidebar collapsed={collapsed} onToggle={() => setCollapsed((value) => !value)}>
        {navLinks}
      </Sidebar>
      <div className="workspace">
        <Header title={current.label} onOpenNavigation={() => menu.current?.showModal()} />
        <main id="main-content" tabIndex={-1}>
          {isPublicDemo && (
            <div className="demo-banner" role="note">
              <p>
                <strong>Public demonstration — synthetic data only</strong>
                <span>
                  No live monitoring, backend connection, semantic retrieval or AI execution.
                  Displayed incidents are bundled examples.
                </span>
              </p>
              <span className="sample-tag">DEMO</span>
            </div>
          )}
          {isHostedApi && (
            <div className="demo-banner" role="note">
              <p>
                <strong>Hosted read-only API — stateless</strong>
                <span>
                  No incident storage, microservice monitoring, historical retrieval or AI execution
                  is deployed. Empty counts are not production activity.
                </span>
              </p>
            </div>
          )}
          {children}
        </main>
        <footer className="app-footer">
          <span>
            OpsGuard AI <span className="muted">/</span>{' '}
            {isPublicDemo
              ? 'Public synthetic demonstration'
              : isHostedApi
                ? 'Hosted API · Stateless'
                : 'Local RAG · Read-only investigations'}
          </span>
          <WorkspaceFooter />
        </footer>
      </div>
      <dialog
        className="mobile-nav-dialog"
        aria-labelledby="navigation-title"
        ref={menu}
        onClick={(event) => {
          if (event.target === menu.current) menu.current?.close();
        }}
      >
        <div className="dialog-header">
          <strong id="navigation-title">OpsGuard AI</strong>
          <button
            className="icon-button"
            aria-label="Close navigation"
            onClick={() => menu.current?.close()}
          >
            <X size={20} />
          </button>
        </div>
        <nav aria-label="Mobile navigation" onClick={() => menu.current?.close()}>
          {navLinks}
        </nav>
      </dialog>
    </div>
  );
}
export function Shell({ children }: { children: React.ReactNode }) {
  return (
    <HealthProvider>
      <MonitoringProvider>
        <WorkspaceShell>{children}</WorkspaceShell>
      </MonitoringProvider>
    </HealthProvider>
  );
}

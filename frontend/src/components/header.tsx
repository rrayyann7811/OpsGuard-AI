import { isPublicDemo, isHostedApi } from '@/lib/runtime-mode';
import Link from 'next/link';
import { Menu } from 'lucide-react';
import { useHealth } from './health-provider';
export function Header({
  title,
  onOpenNavigation,
}: {
  title: string;
  onOpenNavigation: () => void;
}) {
  const { health, loading } = useHealth();
  return (
    <header className="topbar">
      <div className="breadcrumb">
        <button
          className="icon-button mobile-menu"
          aria-label="Open navigation"
          onClick={onOpenNavigation}
        >
          <Menu size={21} />
        </button>
        <span className="muted">Workspace</span>
        <span className="muted">/</span>
        <span>{title}</span>
      </div>
      <div className="topbar-right">
        <span className="environment">
          <span />
          {isPublicDemo ? 'Public demo' : isHostedApi ? 'Hosted API' : 'Development'}
        </span>
        <Link
          href="/settings"
          className={`backend-pill ${health ? 'connected' : ''}`}
          title="View backend connection settings"
        >
          <span className="status-dot" />
          <span aria-live="polite">
            {isPublicDemo
              ? 'Demo — no backend'
              : loading
                ? 'Checking backend'
                : health
                  ? 'Backend connected'
                  : 'Backend offline'}
          </span>
        </Link>
        <span className="avatar" title="Local development workspace">
          OG
        </span>
      </div>
    </header>
  );
}

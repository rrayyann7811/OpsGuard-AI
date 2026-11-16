import { isPublicDemo } from '@/lib/runtime-mode';
import Link from 'next/link';
import { Activity, ArrowUpRight, ChevronLeft, ShieldCheck } from 'lucide-react';
import { apiUrl } from '@/lib/health';
export function Sidebar({
  collapsed,
  onToggle,
  children,
}: {
  collapsed: boolean;
  onToggle: () => void;
  children: React.ReactNode;
}) {
  return (
    <aside className="sidebar">
      <Link className="brand" href="/" aria-label="OpsGuard AI overview">
        <span className="brand-mark">
          <ShieldCheck size={24} />
        </span>
        <span>
          OpsGuard <b>AI</b>
          <small>OPERATIONS WORKSPACE</small>
        </span>
      </Link>
      <div className="workspace-label">
        WORKSPACE <span>01</span>
      </div>
      <nav aria-label="Main navigation">{children}</nav>
      <div className="sidebar-bottom">
        <div className="phase-note">
          <span className="phase-icon">
            <Activity size={17} />
          </span>
          <strong>Evidence before action.</strong>
          <p>Local RAG · Human review</p>
        </div>
        {!isPublicDemo && (
          <a className="sidebar-docs" href={`${apiUrl}/docs`} target="_blank" rel="noreferrer">
            API documentation <ArrowUpRight size={15} />
          </a>
        )}
        <button
          className="collapse-button"
          onClick={onToggle}
          aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          aria-expanded={!collapsed}
        >
          <ChevronLeft size={17} />
          <span>Collapse sidebar</span>
        </button>
      </div>
    </aside>
  );
}

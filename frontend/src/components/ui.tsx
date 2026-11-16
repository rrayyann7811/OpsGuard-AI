import { AlertCircle, ArrowUpRight, Inbox, LoaderCircle } from 'lucide-react';
import type { ReactNode } from 'react';
export function Badge({ label }: { label: string }) {
  return (
    <span className={`badge ${label.toLowerCase().replaceAll(' ', '-')}`}>
      <span aria-hidden="true">
        {label === 'Critical'
          ? '◆'
          : label === 'High'
            ? '▲'
            : label === 'Medium'
              ? '■'
              : label === 'Low'
                ? '▽'
                : '●'}
      </span>
      {label}
    </span>
  );
}
export function StatCard({
  label,
  value,
  detail,
  icon,
}: {
  label: string;
  value: string | number;
  detail: string;
  icon: ReactNode;
}) {
  return (
    <article className="stat-card">
      <div className="stat-label">
        {label}
        <span className="stat-icon">{icon}</span>
      </div>
      <strong>{value}</strong>
      <div className="stat-detail">{detail}</div>
    </article>
  );
}
export function Panel({
  title,
  description,
  action,
  children,
  className = '',
}: {
  title: string;
  description?: string;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={`panel ${className}`}>
      <div className="panel-heading">
        <div>
          <h2>{title}</h2>
          {description && <p>{description}</p>}
        </div>
        {action}
      </div>
      {children}
    </section>
  );
}
export function EmptyState({ title, description }: { title: string; description: string }) {
  return (
    <div className="empty-state">
      <Inbox size={30} />
      <h3>{title}</h3>
      <p>{description}</p>
    </div>
  );
}
export function LoadingState({ label = 'Checking connection…' }: { label?: string }) {
  return (
    <span className="inline-state" role="status">
      <LoaderCircle size={15} className="spin" />
      {label}
    </span>
  );
}
export function ErrorMessage({ message, retry }: { message: string; retry?: () => void }) {
  return (
    <div className="error-message" role="alert">
      <AlertCircle size={18} />
      <span>{message}</span>
      {retry && (
        <button className="text-button" onClick={retry}>
          Retry <ArrowUpRight size={14} />
        </button>
      )}
    </div>
  );
}

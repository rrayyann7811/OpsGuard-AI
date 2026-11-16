import { LoadingState } from '@/components/ui';
export default function Loading() {
  return (
    <div className="empty-state">
      <LoadingState label="Loading workspace…" />
    </div>
  );
}

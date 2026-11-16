'use client';
export default function Error({ reset }: { reset: () => void }) {
  return (
    <div className="empty-state" role="alert">
      <h1>Unable to load this page</h1>
      <p>Try again to reload the workspace.</p>
      <button className="button primary" onClick={reset}>
        Try again
      </button>
    </div>
  );
}

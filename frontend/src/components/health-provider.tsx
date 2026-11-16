'use client';
import { isPublicDemo } from '@/lib/runtime-mode';
import { createContext, useCallback, useContext, useEffect, useState } from 'react';
import { fetchHealth, type Health } from '@/lib/health';
const HealthContext = createContext<{
  health: Health | null;
  loading: boolean;
  error: string | null;
  checkedAt: string | null;
  refresh: () => void;
}>({ health: null, loading: true, error: null, checkedAt: null, refresh: () => {} });
export function HealthProvider({ children }: { children: React.ReactNode }) {
  const [health, setHealth] = useState<Health | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [checkedAt, setCheckedAt] = useState<string | null>(null);
  const [revision, setRevision] = useState(0);
  const refresh = useCallback(() => {
    setLoading(true);
    setRevision((value) => value + 1);
  }, []);
  useEffect(() => {
    const controller = new AbortController();
    fetchHealth(controller.signal)
      .then((result) => {
        if (!controller.signal.aborted) {
          setHealth(result);
          setError(null);
        }
      })
      .catch((cause) => {
        if (!controller.signal.aborted) {
          setHealth(null);
          setError(cause instanceof Error ? cause.message : 'Unable to reach backend');
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setLoading(false);
          setCheckedAt(new Date().toLocaleTimeString());
        }
      });
    return () => controller.abort();
  }, [revision]);
  useEffect(() => {
    if (isPublicDemo) return;
    const timer = setInterval(refresh, 30000);
    return () => clearInterval(timer);
  }, [refresh]);
  return (
    <HealthContext.Provider value={{ health, loading, error, checkedAt, refresh }}>
      {children}
    </HealthContext.Provider>
  );
}
export function useHealth() {
  return useContext(HealthContext);
}

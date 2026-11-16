'use client';
import { useEffect, useSyncExternalStore } from 'react';
export const preferenceKey = 'opsguard.preferences';
function subscribe(callback: () => void) {
  window.addEventListener('opsguard:preferences', callback);
  window.addEventListener('storage', callback);
  return () => {
    window.removeEventListener('opsguard:preferences', callback);
    window.removeEventListener('storage', callback);
  };
}
function snapshot() {
  try {
    return localStorage.getItem(preferenceKey);
  } catch {
    return null;
  }
}
export function usePreferences() {
  const raw = useSyncExternalStore(subscribe, snapshot, () => null);
  let name = 'Development workspace';
  let compact = false;
  try {
    const value = raw ? JSON.parse(raw) : null;
    if (value && typeof value.name === 'string' && value.name.trim()) name = value.name;
    compact = value?.compact === true;
  } catch {
    /* Invalid local data falls back to defaults. */
  }
  return { name, compact };
}
export function WorkspaceFooter() {
  const { name, compact } = usePreferences();
  useEffect(() => {
    document.documentElement.dataset.density = compact ? 'compact' : 'comfortable';
  }, [compact]);
  return <span>{name} · v0.1.0</span>;
}

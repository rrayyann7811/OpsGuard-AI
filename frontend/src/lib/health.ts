import { isPublicDemo } from './runtime-mode';
export const apiUrl = (process.env.NEXT_PUBLIC_API_URL || '').replace(/\/$/, '');
export type Health = {
  status: 'healthy';
  service: string;
  version: string;
  environment: string;
  database: 'connected';
};
export async function fetchHealth(signal?: AbortSignal): Promise<Health> {
  if (isPublicDemo) throw new Error('Public demonstration: no backend is connected.');
  const response = await fetch(`${apiUrl}/api/health`, {
    signal: signal
      ? AbortSignal.any([signal, AbortSignal.timeout(5000)])
      : AbortSignal.timeout(5000),
    cache: 'no-store',
  });
  if (!response.ok) throw new Error(`Backend returned HTTP ${response.status}`);
  const data: unknown = await response.json();
  if (
    !data ||
    typeof data !== 'object' ||
    !('status' in data) ||
    data.status !== 'healthy' ||
    !('database' in data) ||
    data.database !== 'connected' ||
    !('service' in data) ||
    typeof data.service !== 'string' ||
    !('version' in data) ||
    typeof data.version !== 'string' ||
    !('environment' in data) ||
    typeof data.environment !== 'string'
  )
    throw new Error('Unexpected backend health response');
  return data as Health;
}

export type Severity = 'Critical' | 'High' | 'Medium' | 'Low';
export type Incident = {
  id: string;
  title: string;
  service: string;
  severity: Severity;
  status: 'Investigating' | 'Open' | 'Resolved';
  time: string;
  duration: number;
  evidence: string;
};
export const incidents: Incident[] = [
  {
    id: 'INC-1042',
    title: 'Elevated error rate on checkout',
    service: 'checkout-api',
    severity: 'Critical',
    status: 'Investigating',
    time: '14:32',
    duration: 18,
    evidence:
      '14:32:04 ERROR checkout-api\nPOST /checkout → 503\nDatabasePoolTimeout: connection acquisition exceeded 5000ms\n  at CheckoutRepository.createOrder (repository.ts:84)\n\nSample evidence only. No live logs are collected in Phase 1.',
  },
  {
    id: 'INC-1041',
    title: 'Payment processing latency',
    service: 'payment-service',
    severity: 'High',
    status: 'Open',
    time: '14:18',
    duration: 32,
    evidence:
      '14:18:11 WARN payment-service\nPOST /payments p95 latency: 1820ms\nUpstream request exceeded configured timeout.\n\nSample evidence only. Root cause has not been established.',
  },
  {
    id: 'INC-1040',
    title: 'Memory utilization above threshold',
    service: 'inventory-service',
    severity: 'Medium',
    status: 'Open',
    time: '13:56',
    duration: 54,
    evidence:
      '13:56:30 WARN inventory-service\nMemory utilization: 86%\nConfigured sample threshold: 80%\n\nSample evidence only. No container metrics are connected.',
  },
  {
    id: 'INC-1039',
    title: 'Authentication token refresh failures',
    service: 'auth-service',
    severity: 'High',
    status: 'Resolved',
    time: '12:40',
    duration: 24,
    evidence:
      '12:40:08 ERROR auth-service\nToken refresh returned 401\n13:04:08 INFO sample incident marked resolved\n\nSample evidence only. No remediation was executed.',
  },
  {
    id: 'INC-1038',
    title: 'Intermittent gateway timeouts',
    service: 'api-gateway',
    severity: 'Low',
    status: 'Resolved',
    time: '11:22',
    duration: 12,
    evidence:
      '11:22:16 WARN api-gateway\nGET /catalog → 504\n11:34:16 INFO sample incident marked resolved\n\nSample evidence only.',
  },
];
export const services = [
  {
    name: 'api-gateway',
    description: 'Request routing & rate limiting',
    status: 'Healthy',
    latency: 42,
    uptime: '99.98%',
    requests: 1240,
  },
  {
    name: 'auth-service',
    description: 'Identity & access management',
    status: 'Healthy',
    latency: 68,
    uptime: '99.95%',
    requests: 820,
  },
  {
    name: 'checkout-api',
    description: 'Order creation & checkout',
    status: 'Critical',
    latency: 2340,
    uptime: '98.42%',
    requests: 360,
  },
  {
    name: 'payment-service',
    description: 'Payment transaction processing',
    status: 'Degraded',
    latency: 1820,
    uptime: '99.21%',
    requests: 284,
  },
  {
    name: 'inventory-service',
    description: 'Stock availability & allocation',
    status: 'Degraded',
    latency: 184,
    uptime: '99.72%',
    requests: 640,
  },
  {
    name: 'notification-service',
    description: 'Transactional notifications',
    status: 'Healthy',
    latency: 96,
    uptime: '99.99%',
    requests: 420,
  },
] as const;
export const trend = [
  { time: '09:00', requests: 1860, errors: 8 },
  { time: '10:00', requests: 2240, errors: 12 },
  { time: '11:00', requests: 1980, errors: 24 },
  { time: '12:00', requests: 2680, errors: 18 },
  { time: '13:00', requests: 3120, errors: 42 },
  { time: '14:00', requests: 3764, errors: 126 },
];
export function filterIncidents(query: string, severity: string, status: string) {
  const term = query.trim().toLowerCase();
  return incidents.filter(
    (item) =>
      `${item.id} ${item.title} ${item.service}`.toLowerCase().includes(term) &&
      (severity === 'All severities' || item.severity === severity) &&
      (status === 'All statuses' || item.status === status),
  );
}
export const navigation = [
  { slug: '', label: 'Overview', description: 'Your operations, at a glance.' },
  {
    slug: 'incidents',
    label: 'Incidents',
    description: 'Triage, inspect, and understand service disruptions.',
  },
  {
    slug: 'services',
    label: 'Services',
    description: 'A clear view of your microservice landscape.',
  },
  {
    slug: 'investigations',
    label: 'AI Investigations',
    description: 'Follow the evidence. Understand the cause.',
  },
  {
    slug: 'knowledge',
    label: 'Historical Knowledge',
    description: 'Turn past incidents into operational knowledge.',
  },
  {
    slug: 'analytics',
    label: 'Analytics',
    description: 'Understand incident patterns and response performance.',
  },
  {
    slug: 'settings',
    label: 'Settings',
    description: 'Configure your local workspace and connection.',
  },
];

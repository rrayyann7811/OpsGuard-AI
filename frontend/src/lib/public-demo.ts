// Public, authored synthetic fixtures only. No database, model or HTTP access.
import type { Incident } from './monitoring';
const historical = [
  {
    id: 'SYN-PAY-003',
    title: 'Payment ledger database connection failure',
    service_name: 'payment-service',
    symptoms: 'Payment status writes failed with 503 after the ledger database became unreachable.',
    error_type: 'DatabaseConnectionError',
    error_message: 'Payment ledger database connection refused',
    root_cause:
      'The ledger connection address changed without updating the payment-service connection configuration.',
    resolution:
      'Restore ledger connectivity, verify configuration, and reconcile pending records before retrying charges.',
    technology: ['SQL', 'Payment ledger'],
    severity: 'critical',
    incident_date: '2026-03-03',
    source_ref: 'knowledge/data/incidents.json (original synthetic dataset v1)',
    runbook: [
      'Check ledger availability',
      'Restore connection settings',
      'Reconcile status before retrying to avoid double charges',
    ],
    code_context: 'await ledger.recordPayment(payment);',
    http_status: 503,
    synthetic: true,
  },
  {
    id: 'SYN-PAY-004',
    title: 'Fee subtraction introduced payment total regression',
    service_name: 'payment-service',
    symptoms: 'Payment totals were below the base amount after a small arithmetic change.',
    error_type: 'CalculationRegression',
    error_message: 'Payment total violated fee invariant',
    root_cause:
      'A faulty revision subtracted the rounded two-percent processing fee instead of adding it.',
    resolution:
      'Restore integer-cent fee addition and test fixed totals, rounding boundaries and the total invariant.',
    technology: ['Git regression', 'Integer arithmetic'],
    severity: 'high',
    incident_date: '2026-03-04',
    source_ref: 'knowledge/data/incidents.json (original synthetic dataset v1)',
    runbook: [
      'Reproduce with amount_cents 10000',
      'Expect total_cents 10200',
      'Test rounding and fee invariant before release',
    ],
    code_context: 'const total_cents = amount_cents + Math.round(amount_cents * 0.02);',
    http_status: 500,
    synthetic: true,
  },
];
const date = '2026-01-01T12:00:00Z';
const incident: Incident = {
  id: 'DEMO-PAY-001',
  service_name: 'payment-service',
  title: 'Synthetic PaymentFailure: payment-service',
  severity: 'high',
  status: 'OPEN',
  error_type: 'PaymentFailure',
  error_message: 'Synthetic example: payment processor rejection',
  stack_trace: 'Synthetic stack example\n  at processPayment (demo/payment.js:12:3)',
  endpoint: '/simulate/payment-failure',
  http_status: 502,
  occurrence_count: 2,
  error_signature: 'public-synthetic-example',
  first_seen: date,
  last_seen: date,
  created_at: date,
  updated_at: date,
};
const summary = {
  total: 1,
  active: 1,
  critical: 0,
  resolved: 0,
  by_severity: { critical: 0, high: 1, medium: 0, low: 0 },
  history: [{ date: '2026-01-01', events: 2 }],
};
const jobs = {
  total: 0,
  completed: 0,
  running: 0,
  failed: 0,
  cancelled: 0,
  average_duration_ms: null,
};
export function publicDemoData(path: string): unknown {
  const url = new URL(path, 'https://demo.invalid');
  const name = url.pathname;
  const params = url.searchParams;
  function page(items: unknown[], size = 20) {
    const number = Math.max(1, Number(params.get('page')) || 1);
    const limit = Math.max(1, Number(params.get('page_size')) || size);
    return {
      items: items.slice((number - 1) * limit, number * limit),
      total: items.length,
      page: number,
      page_size: limit,
    };
  }
  if (name === '/api/incidents/summary') return summary;
  if (name === '/api/services')
    return {
      items: ['user-service', 'order-service', 'payment-service'].map((service_name) => ({
        service_name,
        status: 'Unknown',
        available: null,
        last_success: null,
        last_attempt: null,
        latency_ms: null,
        failure_reason: 'Public demonstration: live health checks are disabled.',
        consecutive_failures: 0,
        incident_summary: {
          total: service_name === 'payment-service' ? 1 : 0,
          active: service_name === 'payment-service' ? 1 : 0,
          resolved: 0,
        },
      })),
    };
  if (name === '/api/incidents') {
    const matches =
      (!params.get('service') || params.get('service') === incident.service_name) &&
      (!params.get('severity') || params.get('severity') === incident.severity) &&
      (!params.get('status') || params.get('status') === incident.status) &&
      (!params.get('search') ||
        JSON.stringify(incident).toLowerCase().includes(params.get('search')!.toLowerCase()));
    return page(matches ? [incident] : []);
  }
  if (name === `/api/incidents/${incident.id}`) return { incident };
  if (name === `/api/incidents/${incident.id}/events`)
    return page(
      [1, 2].map((index) => ({
        ...incident,
        timestamp: date,
        event_id: `DEMO-EVENT-${index}`,
        request_id: `DEMO-REQUEST-${index}`,
        duration_ms: 0,
      })),
      10,
    );
  if (name === '/api/investigations/summary') return jobs;
  if (name === '/api/investigations') return page([]);
  if (name === '/api/investigations/configuration')
    return {
      available: false,
      mode: 'public-demo',
      backend: 'disabled',
      message: 'Public demonstration: no investigation execution or generated diagnoses.',
      read_only: true,
    };
  if (name === '/api/knowledge/status')
    return {
      status: 'ready',
      mode: 'public synthetic examples',
      collection: 'bundled examples (not Qdrant)',
      indexed_incidents: historical.length,
      indexed_chunks: 0,
      source_count: 1,
      last_indexed_at: null,
      embedding_model: 'Disabled in public demo',
      dimension: 0,
      embedding_loaded: false,
    };
  if (name === '/api/knowledge/incidents')
    return page(
      historical.filter(
        (item) =>
          (!params.get('service') || params.get('service') === item.service_name) &&
          (!params.get('severity') || params.get('severity') === item.severity),
      ),
      6,
    );
  const source = historical.find((item) => name === `/api/knowledge/incidents/${item.id}`);
  if (source) return { incident: source };
  throw new Error('This operation is unavailable in the public demonstration.');
}

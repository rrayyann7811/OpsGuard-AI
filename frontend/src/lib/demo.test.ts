import { describe, expect, it } from 'vitest';
import { filterIncidents, incidents } from './demo';
describe('incident filters', () => {
  it('searches identifiers and service names without case sensitivity', () => {
    expect(filterIncidents(' inc-1042 ', 'All severities', 'All statuses')).toHaveLength(1);
    expect(filterIncidents('PAYMENT', 'All severities', 'All statuses')[0].service).toBe(
      'payment-service',
    );
  });
  it('combines severity and status filters', () => {
    expect(filterIncidents('', 'High', 'Resolved').map((item) => item.id)).toEqual(['INC-1039']);
    expect(filterIncidents('', 'Critical', 'Resolved')).toEqual([]);
  });
  it('returns all incidents when filters are cleared', () => {
    expect(filterIncidents('', 'All severities', 'All statuses')).toEqual(incidents);
  });
});

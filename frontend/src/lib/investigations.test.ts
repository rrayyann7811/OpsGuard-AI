import { describe, expect, it } from 'vitest';
import { executionLabel } from './investigations';

describe('execution provenance', () => {
  it('distinguishes local, managed, simulated and unknown reports', () => {
    expect(executionLabel('test-double')).toBe('TEST DOUBLE — NOT CODEX');
    expect(executionLabel('local-ollama')).toBe('Local AI Investigation');
    expect(executionLabel('live-codex')).toBe('LOCAL CODEX');
    expect(executionLabel('live-managed-codex')).toBe('MANAGED CODEX');
    expect(executionLabel(undefined)).toBe('EXECUTION UNVERIFIED');
    expect(executionLabel('unknown')).toBe('EXECUTION UNVERIFIED');
  });
});

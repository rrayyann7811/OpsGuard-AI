// Deliberately faulty historical revision fixture: regression-fee-v1.
// No Git operations run; the simulator detects this regression against an invariant.
export const total = (amount) => amount - Math.round(amount * 0.02);

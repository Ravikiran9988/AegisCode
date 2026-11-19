import test from 'node:test';
import assert from 'node:assert/strict';
import { calculateDashboardMetrics } from './dashboardMetrics.js';

test('empty history does not invent a pass rate or duration', () => {
  assert.deepEqual(calculateDashboardMetrics([]), {
    totalRuns: 0,
    terminalRuns: 0,
    passedRuns: 0,
    passRate: null,
    averageDuration: null,
  });
});

test('pass rate uses only terminal runs', () => {
  const metrics = calculateDashboardMetrics([
    { status: 'passed', duration: 10 },
    { status: 'failed', duration: 30 },
    { status: 'running', duration: null },
  ]);
  assert.equal(metrics.totalRuns, 3);
  assert.equal(metrics.terminalRuns, 2);
  assert.equal(metrics.passedRuns, 1);
  assert.equal(metrics.passRate, 50);
  assert.equal(metrics.averageDuration, 20);
});

test('missing and invalid durations are excluded', () => {
  const metrics = calculateDashboardMetrics([
    { status: 'passed', duration: 12 },
    { status: 'failed', duration: null },
    { status: 'timeout', duration: 'unknown' },
    { status: 'cancelled', duration: -4 },
  ]);
  assert.equal(metrics.averageDuration, 12);
});

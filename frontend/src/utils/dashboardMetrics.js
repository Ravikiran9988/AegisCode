const TERMINAL_STATUSES = new Set([
  'passed',
  'already_passing',
  'failed',
  'stalled',
  'error',
  'cancelled',
  'partially_repaired',
  'reviewer_rejected',
  'test_error',
  'timeout',
]);

export function calculateDashboardMetrics(runs = []) {
  const records = Array.isArray(runs) ? runs : [];
  const terminalRuns = records.filter((run) => TERMINAL_STATUSES.has(run?.status));
  const passedRuns = terminalRuns.filter(
    (run) => run.status === 'passed' || run.status === 'already_passing'
  ).length;

  const durations = terminalRuns
    .map((run) => run?.duration)
    .filter((duration) => typeof duration === 'number' && Number.isFinite(duration) && duration >= 0);

  return {
    totalRuns: records.length,
    terminalRuns: terminalRuns.length,
    passedRuns,
    passRate: terminalRuns.length
      ? Math.round((passedRuns / terminalRuns.length) * 100)
      : null,
    averageDuration: durations.length
      ? Math.round(durations.reduce((total, duration) => total + duration, 0) / durations.length)
      : null,
  };
}

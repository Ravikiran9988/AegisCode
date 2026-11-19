import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import {
  PlayCircle,
  Activity,
  CheckCircle2,
  Clock,
  Sparkles,
  ArrowRight,
  ShieldCheck,
  AlertCircle,
  RefreshCw,
} from 'lucide-react';
import StatCard from '../components/StatCard';
import { listRuns, listActiveRuns } from '../api/runs';
import { calculateDashboardMetrics } from '../utils/dashboardMetrics';

export default function Overview() {
  const [runs, setRuns] = useState([]);
  const [activeRuns, setActiveRuns] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState('');

  const fetchData = async () => {
    setIsLoading(true);
    try {
      const [allRunsData, activeRunsData] = await Promise.all([
        listRuns(100),
        listActiveRuns(),
      ]);
      setLoadError('');
      setRuns(allRunsData || []);
      setActiveRuns(activeRunsData || []);
    } catch (err) {
      setLoadError(err.message || 'Could not load repair metrics.');
      console.error('Failed to load overview data:', err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 10000);
    return () => clearInterval(interval);
  }, []);

  // Metrics are calculated only from real API records. Empty histories stay empty.
  const metrics = calculateDashboardMetrics(runs);
  const totalRuns = metrics.totalRuns;
  const passRate = metrics.passRate === null ? '—' : `${metrics.passRate}%`;
  const avgDuration =
    metrics.averageDuration === null ? '—' : `${metrics.averageDuration}s`;


  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-wrap items-center justify-between gap-4 pb-4 border-b border-slate-200 dark:border-slate-800">
        <div>
          <h2 className="text-xl font-bold tracking-tight text-slate-900 dark:text-slate-100 flex items-center gap-2">
            <span>Fixsembly Control Center</span>
            <span className="text-xs font-mono font-medium px-2 py-0.5 rounded-full bg-brand-500/10 text-brand-600 dark:text-brand-400 border border-brand-500/20">
              Live Hub
            </span>
          </h2>
          <p className="text-xs text-slate-600 dark:text-slate-400 mt-1">
            Real-time telemetry and multi-agent repair operations.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={fetchData}
            disabled={isLoading}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 hover:bg-slate-100 dark:hover:bg-slate-800 text-xs font-mono text-slate-700 dark:text-slate-300 shadow-sm transition"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${isLoading ? 'animate-spin' : ''}`} />
            <span>Refresh</span>
          </button>
          <Link
            to="/repair/new"
            className="flex items-center gap-1.5 px-4 py-1.5 rounded-xl bg-gradient-to-r from-brand-600 to-indigo-600 hover:from-brand-500 hover:to-indigo-500 text-xs font-semibold text-white shadow-md shadow-brand-500/20 transition"
          >
            <PlayCircle className="h-4 w-4" />
            <span>New Repair Run</span>
          </Link>
        </div>
      </div>

      {loadError && (
        <div role="alert" className="rounded-xl border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-xs text-rose-700 dark:text-rose-300">
          Unable to refresh dashboard data: {loadError}
        </div>
      )}

      {/* Active Runs Banner */}
      {activeRuns.length > 0 && (
        <div className="rounded-2xl border border-brand-500/30 bg-brand-500/10 p-4 flex flex-wrap items-center justify-between gap-4 animate-pulse">
          <div className="flex items-center gap-3">
            <div className="h-3 w-3 rounded-full bg-brand-500 dark:bg-brand-400 animate-ping"></div>
            <div>
              <p className="text-xs font-semibold text-brand-700 dark:text-brand-200">
                {activeRuns.length} Active Autonomous Repair{activeRuns.length > 1 ? 's' : ''} in Progress
              </p>
              <p className="text-[11px] text-brand-600/80 dark:text-brand-300/80">
                Agents are actively analyzing, patching, and verifying test assertions.
              </p>
            </div>
          </div>
          <Link
            to={`/repair/${activeRuns[0].run_id}`}
            className="flex items-center gap-1.5 text-xs font-mono font-semibold px-3 py-1 rounded-lg bg-brand-600 text-white hover:bg-brand-500 transition"
          >
            <span>Open Studio</span>
            <ArrowRight className="h-3 w-3" />
          </Link>
        </div>
      )}

      {/* Telemetry Stats */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title="Total Repairs"
          value={totalRuns}
          subtext="Latest repair executions"
          icon={Activity}
          color="brand"
        />
        <StatCard
          title="Recent Verified Pass Rate"
          value={passRate}
          subtext="Green pytest verification"
          icon={CheckCircle2}
          color="emerald"
          
        />
        <StatCard
          title="Active Repairs"
          value={activeRuns.length}
          subtext="In-flight agent jobs"
          icon={Sparkles}
          color="blue"
        />
        <StatCard
          title="Average Duration"
          value={avgDuration}
          subtext="Completed runs with duration data"
          icon={Clock}
          color="amber"
        />
      </div>

      {/* Recent Repairs Table */}
      <div className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900/40 overflow-hidden shadow-sm backdrop-blur-sm">
        <div className="flex items-center justify-between p-4 border-b border-slate-200 dark:border-slate-800">
          <div>
            <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100">Recent Repair Executions</h3>
            <p className="text-xs text-slate-600 dark:text-slate-400">Click any run to view real-time agent telemetry</p>
          </div>
          <Link
            to="/history"
            className="text-xs font-mono text-brand-600 dark:text-brand-400 hover:text-brand-500 dark:hover:text-brand-300 flex items-center gap-1"
          >
            <span>View All</span>
            <ArrowRight className="h-3 w-3" />
          </Link>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-100/80 dark:bg-slate-950/70 border-b border-slate-200 dark:border-slate-800 text-slate-600 dark:text-slate-400 uppercase font-mono text-[10px]">
              <tr>
                <th className="px-4 py-3">Run ID</th>
                <th className="px-4 py-3">Project</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Iteration</th>
                <th className="px-4 py-3">Pytest Truth</th>
                <th className="px-4 py-3">Duration</th>
                <th className="px-4 py-3 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-slate-800/60 font-mono text-slate-700 dark:text-slate-300">
              {runs.length === 0 ? (
                <tr>
                  <td colSpan="7" className="text-center py-8 text-slate-500 font-sans">
                    No repair runs executed yet. Click "New Repair Run" to begin.
                  </td>
                </tr>
              ) : (
                runs.map((r) => {
                  const isPass = r.status === 'passed' || r.status === 'already_passing';
                  const isFail =
                    r.status === 'failed' ||
                    r.status === 'error' ||
                    r.status === 'cancelled' ||
                    r.status === 'test_error' ||
                    r.status === 'timeout';
                  const isWarn =
                    r.status === 'stalled' ||
                    r.status === 'partially_repaired' ||
                    r.status === 'reviewer_rejected';

                  return (
                    <tr key={r.run_id} className="hover:bg-slate-50 dark:hover:bg-slate-800/30 transition">
                      <td className="px-4 py-3 font-semibold text-brand-600 dark:text-brand-400">
                        {r.run_id.slice(0, 8)}
                      </td>
                      <td className="px-4 py-3 font-sans font-medium text-slate-900 dark:text-slate-200">
                        {r.project_name || 'Project'}
                      </td>
                      <td className="px-4 py-3">
                        <span
                          className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] uppercase font-semibold border ${
                            isPass
                              ? 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20'
                              : isFail
                              ? 'bg-rose-500/10 text-rose-600 dark:text-rose-400 border-rose-500/20'
                              : isWarn
                              ? 'bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/20'
                              : 'bg-brand-500/10 text-brand-600 dark:text-brand-400 border-brand-500/20 animate-pulse'
                          }`}
                        >
                          {r.status}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-slate-600 dark:text-slate-400">
                        {r.current_iteration} / {r.max_iterations}
                      </td>
                      <td className="px-4 py-3">
                        {r.tests_passed !== null && r.tests_passed !== undefined ? (
                          <span className="text-emerald-600 dark:text-emerald-400">{r.tests_passed} passed</span>
                        ) : isPass ? (
                          <span className="text-emerald-600 dark:text-emerald-400">All Passed</span>
                        ) : (
                          <span className="text-slate-500">-</span>
                        )}
                        {r.tests_failed ? (
                          <span className="text-rose-600 dark:text-rose-400 ml-1.5">({r.tests_failed} failed)</span>
                        ) : null}
                      </td>
                      <td className="px-4 py-3 text-slate-600 dark:text-slate-400">
                        {r.duration ? `${Math.round(r.duration)}s` : '-'}
                      </td>
                      <td className="px-4 py-3 text-right">
                        <Link
                          to={`/repair/${r.run_id}`}
                          className="text-xs font-sans text-brand-600 dark:text-brand-400 hover:text-brand-500 dark:hover:text-brand-300 font-medium inline-flex items-center gap-1"
                        >
                          <span>Studio</span>
                          <ArrowRight className="h-3 w-3" />
                        </Link>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

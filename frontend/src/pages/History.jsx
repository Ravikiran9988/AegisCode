import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import {
  History as HistoryIcon,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  ArrowRight,
  Download,
  Filter,
  RefreshCw,
} from 'lucide-react';
import { listRuns } from '../api/runs';

export default function History() {
  const [runs, setRuns] = useState([]);
  const [filterStatus, setFilterStatus] = useState('all');
  const [isLoading, setIsLoading] = useState(true);

  const fetchRuns = async () => {
    setIsLoading(true);
    try {
      const data = await listRuns(50, filterStatus === 'all' ? null : filterStatus);
      setRuns(data || []);
    } catch (err) {
      console.error('Failed to load history:', err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchRuns();
  }, [filterStatus]);

  const handleDownload = (e, runId) => {
    e.stopPropagation();
    const downloadUrl = `/api/runs/${runId}/download`;
    const a = document.createElement('a');
    a.href = downloadUrl;
    a.download = `fixsembly-repaired-${runId.slice(0, 8)}.zip`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-4 pb-4 border-b border-slate-200 dark:border-slate-800">
        <div>
          <h2 className="text-xl font-bold tracking-tight text-slate-900 dark:text-slate-100 flex items-center gap-2">
            <HistoryIcon className="h-5 w-5 text-brand-600 dark:text-brand-400" />
            <span>Repair History & Run Logs</span>
          </h2>
          <p className="text-xs text-slate-600 dark:text-slate-400 mt-1">
            Historical audit logs of previous multi-agent repair executions.
          </p>
        </div>

        <button
          onClick={fetchRuns}
          disabled={isLoading}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 hover:bg-slate-100 dark:hover:bg-slate-800 text-xs font-mono text-slate-700 dark:text-slate-300 shadow-sm transition"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${isLoading ? 'animate-spin' : ''}`} />
          <span>Refresh Logs</span>
        </button>
      </div>

      {/* Filter Tabs */}
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-xs font-mono text-slate-500 flex items-center gap-1 mr-1">
          <Filter className="h-3 w-3" /> Filter:
        </span>
        <div className="flex flex-wrap gap-1.5">
          {[
            { value: 'all', label: 'ALL' },
            { value: 'passed', label: 'PASSED' },
            { value: 'failed', label: 'FAILED' },
            { value: 'stalled', label: 'STALLED' },
            { value: 'test_error', label: 'TEST ERROR' },
            { value: 'cancelled', label: 'CANCELLED' },
          ].map(({ value, label }) => (
            <button
              key={value}
              onClick={() => setFilterStatus(value)}
              className={`px-3 py-1.5 rounded-xl text-xs font-mono font-medium transition border ${
                filterStatus === value
                  ? 'bg-brand-600 text-white border-brand-500 shadow-sm'
                  : 'bg-white dark:bg-slate-900 border-slate-200 dark:border-slate-800 text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200 shadow-sm'
              }`}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      {/* Runs Table */}
      <div className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900/40 overflow-hidden shadow-sm backdrop-blur-sm">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-100/80 dark:bg-slate-950/70 border-b border-slate-200 dark:border-slate-800 text-slate-600 dark:text-slate-400 uppercase font-mono text-[10px]">
              <tr>
                <th className="px-4 py-3">Run ID</th>
                <th className="px-4 py-3">Project</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Iterations</th>
                <th className="px-4 py-3">Summary / Diagnosis</th>
                <th className="px-4 py-3">Duration</th>
                <th className="px-4 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-slate-800/60 font-mono text-slate-700 dark:text-slate-300">
              {runs.length === 0 ? (
                <tr>
                  <td colSpan="7" className="text-center py-10 text-slate-500 font-sans">
                    {isLoading ? 'Loading historical runs...' : 'No runs match the selected filter.'}
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
                          className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] uppercase font-semibold border ${
                            isPass
                              ? 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20'
                              : isFail
                              ? 'bg-rose-500/10 text-rose-600 dark:text-rose-400 border-rose-500/20'
                              : isWarn
                              ? 'bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/20'
                              : 'bg-brand-500/10 text-brand-600 dark:text-brand-400 border-brand-500/20'
                          }`}
                        >
                          {r.status}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-slate-600 dark:text-slate-400">
                        {r.current_iteration} / {r.max_iterations}
                      </td>
                      <td className="px-4 py-3 font-sans text-xs text-slate-600 dark:text-slate-400 max-w-xs truncate">
                        {r.final_summary || 'Diagnosis in progress...'}
                      </td>
                      <td className="px-4 py-3 text-slate-600 dark:text-slate-400">
                        {r.duration ? `${Math.round(r.duration)}s` : '-'}
                      </td>
                      <td className="px-4 py-3 text-right">
                        <div className="flex items-center justify-end gap-2">
                          {isPass && (
                            <button
                              onClick={(e) => handleDownload(e, r.run_id)}
                              className="text-slate-400 hover:text-emerald-600 dark:hover:text-emerald-400 transition"
                              title="Download verified zip"
                            >
                              <Download className="h-3.5 w-3.5" />
                            </button>
                          )}
                          <Link
                            to={`/repair/${r.run_id}`}
                            className="text-xs font-sans text-brand-600 dark:text-brand-400 hover:text-brand-500 dark:hover:text-brand-300 font-medium inline-flex items-center gap-1"
                          >
                            <span>Studio</span>
                            <ArrowRight className="h-3 w-3" />
                          </Link>
                        </div>
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

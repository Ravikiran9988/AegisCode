import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import {
  History as HistoryIcon,
  Download,
  ArrowRight,
  Filter,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  RefreshCw,
} from 'lucide-react';
import { listHistoryRuns, downloadRunZip } from '../api/runs';
import { useToast } from '../context/ToastContext';

export default function History() {
  const toast = useToast();
  const [runs, setRuns] = useState([]);
  const [filterStatus, setFilterStatus] = useState('');
  const [isLoading, setIsLoading] = useState(true);

  const fetchRuns = async () => {
    setIsLoading(true);
    try {
      const data = await listHistoryRuns(filterStatus || null);
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

  const handleDownload = async (runId) => {
    try {
      toast.info('Packaging verified fix archive...');
      const blob = await downloadRunZip(runId);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `fixsembly-repaired-${runId.slice(0, 8)}.zip`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
      toast.success('Download started! Repaired project saved.');
    } catch (err) {
      toast.error(`Download failed: ${err.message}`);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-4 pb-4 border-b border-slate-800">
        <div>
          <h2 className="text-xl font-bold tracking-tight text-white flex items-center gap-2">
            <HistoryIcon className="h-5 w-5 text-brand-400" />
            <span>Repair Run History</span>
          </h2>
          <p className="text-xs text-slate-400 mt-1">
            Historical audit records and verified fix downloads.
          </p>
        </div>

        {/* Filter Pills */}
        <div className="flex items-center gap-2">
          {['', 'passed', 'failed', 'stalled'].map((status) => (
            <button
              key={status}
              onClick={() => setFilterStatus(status)}
              className={`px-3 py-1.5 rounded-xl text-xs font-mono font-medium transition border ${
                filterStatus === status
                  ? 'bg-brand-600 text-white border-brand-500 shadow-sm'
                  : 'bg-slate-900 border-slate-800 text-slate-400 hover:text-slate-200'
              }`}
            >
              {status === '' ? 'All Records' : status.toUpperCase()}
            </button>
          ))}
        </div>
      </div>

      {/* Runs Table */}
      <div className="rounded-2xl border border-slate-800 bg-slate-900/40 overflow-hidden backdrop-blur-sm">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-950/70 border-b border-slate-800 text-slate-400 uppercase font-mono text-[10px]">
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
            <tbody className="divide-y divide-slate-800/60 font-mono text-slate-300">
              {runs.length === 0 ? (
                <tr>
                  <td colSpan="7" className="text-center py-10 text-slate-500 font-sans">
                    {isLoading ? 'Loading historical runs...' : 'No runs match the selected filter.'}
                  </td>
                </tr>
              ) : (
                runs.map((r) => {
                  const isPass = r.status === 'passed' || r.status === 'already_passing';
                  const isFail = r.status === 'failed' || r.status === 'error';
                  const isStalled = r.status === 'stalled';

                  return (
                    <tr key={r.run_id} className="hover:bg-slate-800/30 transition">
                      <td className="px-4 py-3 font-semibold text-brand-400">
                        {r.run_id.slice(0, 8)}
                      </td>
                      <td className="px-4 py-3 font-sans font-medium text-slate-200">
                        {r.project_name || 'Project'}
                      </td>
                      <td className="px-4 py-3">
                        <span
                          className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] uppercase font-semibold border ${
                            isPass
                              ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                              : isFail
                              ? 'bg-rose-500/10 text-rose-400 border-rose-500/20'
                              : isStalled
                              ? 'bg-amber-500/10 text-amber-400 border-amber-500/20'
                              : 'bg-brand-500/10 text-brand-400 border-brand-500/20'
                          }`}
                        >
                          {r.status}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-slate-400">
                        {r.current_iteration} / {r.max_iterations}
                      </td>
                      <td className="px-4 py-3 font-sans text-xs text-slate-400 max-w-xs truncate">
                        {r.final_summary || 'Autonomous repair run'}
                      </td>
                      <td className="px-4 py-3 text-slate-400">
                        {r.duration ? `${Math.round(r.duration)}s` : '-'}
                      </td>
                      <td className="px-4 py-3 text-right">
                        <div className="flex items-center justify-end gap-2 font-sans">
                          {isPass && (
                            <button
                              onClick={() => handleDownload(r.run_id)}
                              className="p-1 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-emerald-400 transition"
                              title="Download verified fix ZIP"
                            >
                              <Download className="h-3.5 w-3.5" />
                            </button>
                          )}
                          <Link
                            to={`/repair/${r.run_id}`}
                            className="text-xs text-brand-400 hover:text-brand-300 font-medium inline-flex items-center gap-1 ml-1"
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

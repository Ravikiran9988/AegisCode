import { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import {
  Download,
  Terminal as TerminalIcon,
  Code2,
  ShieldCheck,
  History,
  Sparkles,
  ArrowLeft,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Clock,
  Layers,
  FileText,
} from 'lucide-react';
import AgentStepper from '../components/AgentStepper';
import MonacoDiff from '../components/MonacoDiff';
import Terminal from '../components/Terminal';
import ReviewAudit from '../components/ReviewAudit';
import { useRunStream } from '../api/sse';
import { getRunResults, downloadRunZip, cancelRun } from '../api/runs';
import { useToast } from '../context/ToastContext';

export default function RepairStudio() {
  const { runId } = useParams();
  const toast = useToast();
  const [activeTab, setActiveTab] = useState('diff'); // 'diff', 'terminal', 'review', 'timeline'
  const [resultsData, setResultsData] = useState(null);
  const [isDownloading, setIsDownloading] = useState(false);
  const [isCancelling, setIsCancelling] = useState(false);

  // Hook into live Server-Sent Events stream
  const { data: statusData, isStreaming, refresh } = useRunStream(runId, {
    onComplete: () => {
      // Fetch full iteration results once completed
      getRunResults(runId).then(setResultsData).catch(console.error);
    },
  });

  useEffect(() => {
    // Initial fetch of results if run is already completed
    getRunResults(runId).then(setResultsData).catch(console.error);
  }, [runId]);

  const handleDownload = async () => {
    setIsDownloading(true);
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
    } finally {
      setIsDownloading(false);
    }
  };

  const handleCancel = async () => {
    if (!window.confirm('Are you sure you want to cancel this repair run?')) return;
    setIsCancelling(true);
    try {
      await cancelRun(runId);
      toast.info('Repair run cancelled.');
      refresh();
    } catch (err) {
      toast.error(`Cancellation failed: ${err.message}`);
    } finally {
      setIsCancelling(false);
    }
  };

  const currentIter = statusData?.current_iteration || 1;
  const isTerminal = [
    'passed', 'already_passing', 'partially_repaired',
    'failed', 'stalled', 'error', 'cancelled',
    'test_error', 'reviewer_rejected', 'timeout',
  ].includes(statusData?.status);
  const isSuccess = statusData?.status === 'passed' || statusData?.status === 'already_passing';

  // Extract latest iteration code changes and test output
  const latestIteration = resultsData?.iterations?.length
    ? resultsData.iterations[resultsData.iterations.length - 1]
    : null;

  const testStdout =
    latestIteration?.test_results?.stdout ||
    latestIteration?.test_results?.stderr ||
    statusData?.failure_diagnostics ||
    'Pytest execution underway...';

  const diffData = statusData?.latest_diff || (latestIteration?.code_changes ? { diff: latestIteration.code_changes[0]?.patch } : null);
  const codeChange = latestIteration?.code_changes?.[0] || statusData?.code_change;
  const reviewResult = latestIteration?.review_result || statusData?.review_result;
  const archPlan = latestIteration?.architecture_plan || statusData?.architecture_plan;

  return (
    <div className="space-y-6">
      {/* Top Navigation & Status Bar */}
      <div className="flex flex-wrap items-center justify-between gap-4 pb-4 border-b border-slate-800">
        <div className="flex items-center gap-3">
          <Link
            to="/overview"
            className="p-1.5 rounded-xl border border-slate-800 bg-slate-900 text-slate-400 hover:text-slate-100 hover:border-slate-700 transition"
            title="Back to Overview"
          >
            <ArrowLeft className="h-4 w-4" />
          </Link>

          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-lg font-bold text-slate-100 tracking-tight">
                Repair Studio
              </h2>
              <span className="font-mono text-xs text-brand-400 bg-brand-500/10 border border-brand-500/20 px-2 py-0.5 rounded-lg">
                RUN-{runId?.slice(0, 8)}
              </span>
            </div>
            <p className="text-xs text-slate-400 mt-0.5">
              Project: <span className="text-slate-200 font-medium">{statusData?.project_name || 'Loading...'}</span>
            </p>
          </div>
        </div>

        {/* Action Controls */}
        <div className="flex items-center gap-3">
          {/* Cancel Button when in-flight */}
          {!isTerminal && (
            <button
              onClick={handleCancel}
              disabled={isCancelling}
              className="flex items-center gap-1.5 text-xs font-semibold px-3.5 py-2 rounded-xl transition border border-rose-500/30 bg-rose-500/10 hover:bg-rose-500/20 text-rose-300 shadow-sm"
              title="Cancel in-progress repair"
            >
              <XCircle className="h-3.5 w-3.5" />
              <span>{isCancelling ? 'Cancelling...' : 'Cancel Run'}</span>
            </button>
          )}

          {/* Download Verified Zip Button */}
          <button
            onClick={handleDownload}
            disabled={!isSuccess || isDownloading}
            className={`flex items-center gap-2 text-xs font-semibold px-4 py-2 rounded-xl transition shadow-md ${isSuccess
              ? 'bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white shadow-emerald-500/20'
              : 'bg-slate-900 border border-slate-800 text-slate-500 cursor-not-allowed opacity-60'
              }`}
            title={isSuccess ? 'Download verified fix archive' : 'Available when tests pass and review is approved'}
          >
            <Download className="h-3.5 w-3.5" />
            <span>{isDownloading ? 'Downloading...' : 'Download Verified Fix (.ZIP)'}</span>
          </button>
        </div>
      </div>

      {/* Status Notification Banners */}
      {isSuccess && (
        <div className="rounded-2xl border border-emerald-500/30 bg-emerald-500/10 p-4 flex flex-wrap items-center justify-between gap-3 text-emerald-300 text-xs animate-in fade-in">
          <div className="flex items-center gap-3">
            <div className="h-8 w-8 rounded-xl bg-emerald-500/20 border border-emerald-500/30 flex items-center justify-center text-emerald-400 flex-shrink-0">
              <CheckCircle2 className="h-5 w-5" />
            </div>
            <div>
              <p className="font-bold text-emerald-200 text-sm">
                Repair Completed & Verified: Red to Green!
              </p>
              <p className="text-emerald-400/80">
                All Pytest assertions passed and the Reviewer Agent verified zero regression risk.
              </p>
            </div>
          </div>
          <button
            onClick={handleDownload}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-semibold transition shadow-sm"
          >
            <Download className="h-3.5 w-3.5" />
            <span>Download ZIP</span>
          </button>
        </div>
      )}

      {statusData?.status === 'partially_repaired' && (
        <div className="rounded-2xl border border-amber-500/30 bg-amber-500/10 p-4 flex items-center gap-3 text-amber-300 text-xs animate-in fade-in">
          <div className="h-8 w-8 rounded-xl bg-amber-500/20 border border-amber-500/30 flex items-center justify-center text-amber-400 flex-shrink-0">
            <AlertTriangle className="h-5 w-5" />
          </div>
          <div>
            <p className="font-bold text-amber-200 text-sm">
              Partially Repaired: Substantial Progress Made
            </p>
            <p className="text-amber-400/80">
              Failing tests were reduced, but remaining assertions exceeded max iteration bounds ({statusData?.max_iterations || 5}).
            </p>
          </div>
        </div>
      )}

      {statusData?.status === 'reviewer_rejected' && (
        <div className="rounded-2xl border border-orange-500/30 bg-orange-500/10 p-4 flex items-center gap-3 text-orange-300 text-xs animate-in fade-in">
          <div className="h-8 w-8 rounded-xl bg-orange-500/20 border border-orange-500/30 flex items-center justify-center text-orange-400 flex-shrink-0">
            <AlertTriangle className="h-5 w-5" />
          </div>
          <div>
            <p className="font-bold text-orange-200 text-sm">
              Reviewer Audit Gate Flagged Regression Risk
            </p>
            <p className="text-orange-400/80">
              Pytest assertions passed, but the Reviewer Agent rejected the patch due to security or regression risks.
            </p>
          </div>
        </div>
      )}

      {statusData?.status === 'test_error' && (
        <div className="rounded-2xl border border-rose-500/30 bg-rose-500/10 p-4 flex items-center gap-3 text-rose-300 text-xs animate-in fade-in">
          <div className="h-8 w-8 rounded-xl bg-rose-500/20 border border-rose-500/30 flex items-center justify-center text-rose-400 flex-shrink-0">
            <XCircle className="h-5 w-5" />
          </div>
          <div>
            <p className="font-bold text-rose-200 text-sm">
              Test Execution Error
            </p>
            <p className="text-rose-400/80">
              Pytest execution encountered a collection error or syntax crash. Check terminal logs for trace details.
            </p>
          </div>
        </div>
      )}

      {statusData?.status === 'cancelled' && (
        <div className="rounded-2xl border border-slate-700 bg-slate-900/60 p-4 flex items-center gap-3 text-slate-300 text-xs animate-in fade-in">
          <div className="h-8 w-8 rounded-xl bg-slate-800 border border-slate-700 flex items-center justify-center text-slate-400 flex-shrink-0">
            <XCircle className="h-5 w-5" />
          </div>
          <div>
            <p className="font-bold text-slate-200 text-sm">
              Repair Run Cancelled
            </p>
            <p className="text-slate-400">
              The repair process was terminated by user request.
            </p>
          </div>
        </div>
      )}

      {/* Multi-Agent Stepper Visualizer */}
      <AgentStepper statusData={statusData} />

      {/* Tab Navigation */}
      <div className="flex items-center gap-2 border-b border-slate-800/80 pb-px">
        <button
          onClick={() => setActiveTab('diff')}
          className={`flex items-center gap-2 px-4 py-2.5 text-xs font-medium border-b-2 transition ${activeTab === 'diff'
            ? 'border-brand-500 text-brand-300 font-semibold'
            : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
        >
          <Code2 className="h-4 w-4" />
          <span>Synthesized Diffs</span>
        </button>

        <button
          onClick={() => setActiveTab('terminal')}
          className={`flex items-center gap-2 px-4 py-2.5 text-xs font-medium border-b-2 transition ${activeTab === 'terminal'
            ? 'border-brand-500 text-brand-300 font-semibold'
            : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
        >
          <TerminalIcon className="h-4 w-4" />
          <span>Pytest Truth Terminal</span>
        </button>

        <button
          onClick={() => setActiveTab('review')}
          className={`flex items-center gap-2 px-4 py-2.5 text-xs font-medium border-b-2 transition ${activeTab === 'review'
            ? 'border-brand-500 text-brand-300 font-semibold'
            : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
        >
          <ShieldCheck className="h-4 w-4" />
          <span>Reviewer Audit Gate</span>
        </button>

        <button
          onClick={() => setActiveTab('timeline')}
          className={`flex items-center gap-2 px-4 py-2.5 text-xs font-medium border-b-2 transition ${activeTab === 'timeline'
            ? 'border-brand-500 text-brand-300 font-semibold'
            : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
        >
          <History className="h-4 w-4" />
          <span>Agent Timeline</span>
        </button>
      </div>

      {/* Tab Contents */}
      <div>
        {activeTab === 'diff' && (
          <div className="space-y-4">
            {/* Architecture Plan Card */}
            {archPlan && (
              <div className="rounded-2xl border border-slate-800/80 bg-slate-900/60 p-4 text-xs">
                <div className="flex items-center gap-2 mb-2">
                  <Sparkles className="h-4 w-4 text-brand-400" />
                  <h4 className="font-semibold text-slate-200">Architect Agent Strategy</h4>
                </div>
                <p className="text-slate-300 leading-relaxed font-sans">{archPlan.summary}</p>
                {archPlan.relevant_files?.length > 0 && (
                  <div className="mt-2.5 pt-2 border-t border-slate-800/60 flex items-center gap-2 text-[11px] font-mono text-slate-400">
                    <span className="text-slate-500">Target Files:</span>
                    {archPlan.relevant_files.map((f, i) => (
                      <span key={i} className="px-1.5 py-0.5 rounded bg-slate-800 text-brand-300">
                        {f}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* Monaco Side-by-Side Diff Editor */}
            <MonacoDiff diffData={diffData} codeChange={codeChange} />
          </div>
        )}

        {activeTab === 'terminal' && (
          <Terminal
            output={testStdout}
            title={`Pytest Truth Console • Iteration ${currentIter}`}
            isRunning={statusData?.status === 'running'}
          />
        )}

        {activeTab === 'review' && (
          <div className="max-w-2xl mx-auto py-2">
            <ReviewAudit reviewResult={reviewResult} />
          </div>
        )}

        {activeTab === 'timeline' && (
          <div className="rounded-2xl border border-slate-800/80 bg-slate-900/60 p-5">
            <h4 className="text-xs font-semibold text-slate-200 uppercase tracking-wider font-mono mb-4">
              Agent Execution Log
            </h4>
            <div className="space-y-3 font-mono text-xs">
              {(statusData?.timeline || []).length === 0 ? (
                <p className="text-slate-500">Waiting for agent events...</p>
              ) : (
                statusData.timeline.map((ev, i) => (
                  <div
                    key={i}
                    className="flex items-start gap-3 p-2.5 rounded-xl border border-slate-800/60 bg-slate-950/40"
                  >
                    <span className="text-slate-500 text-[10px] w-16 flex-shrink-0 pt-0.5">
                      {ev.time || `T+${i}s`}
                    </span>
                    <span className="px-2 py-0.5 rounded text-[10px] uppercase font-semibold bg-brand-500/10 text-brand-400 border border-brand-500/20">
                      {ev.agent}
                    </span>
                    <span className="text-slate-300 font-sans text-xs flex-1">
                      {ev.description || ev.event_type}
                    </span>
                  </div>
                ))
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

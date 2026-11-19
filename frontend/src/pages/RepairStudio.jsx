import { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import {
  Code2,
  Terminal as TerminalIcon,
  ShieldCheck,
  History,
  Download,
  XCircle,
  CheckCircle2,
  AlertTriangle,
  ArrowLeft,
  Sparkles,
  Loader2,
} from 'lucide-react';
import AgentStepper from '../components/AgentStepper';
import Terminal from '../components/Terminal';
import MonacoDiff from '../components/MonacoDiff';
import ReviewAudit from '../components/ReviewAudit';
import { getRunStatus, getRunResults, cancelRun, downloadRunZip } from '../api/runs';
import { useRunStream } from '../api/sse';

export default function RepairStudio() {
  const { runId } = useParams();
  const [activeTab, setActiveTab] = useState('diff'); // 'diff' | 'terminal' | 'review' | 'timeline'
  const [statusData, setStatusData] = useState(null);
  const [testResults, setTestResults] = useState(null);
  const [isCancelling, setIsCancelling] = useState(false);
  const [isDownloading, setIsDownloading] = useState(false);

  // SSE real-time streaming updates
  const { isStreaming } = useRunStream(runId, {
    enabled: true,
    onComplete: () => {
      // Refresh status and results on final terminal state
      loadData();
    },
  });

  const loadData = async () => {
    if (!runId) return;
    try {
      const [statusRes, resultsRes] = await Promise.all([
        getRunStatus(runId).catch(() => null),
        getRunResults(runId).catch(() => null),
      ]);
      if (statusRes) setStatusData(statusRes);
      if (resultsRes) setTestResults(resultsRes);
    } catch (err) {
      console.error('Failed to load repair studio data:', err);
    }
  };

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 5000);
    return () => clearInterval(interval);
  }, [runId]);

  const handleCancel = async () => {
    if (!runId || isCancelling) return;
    setIsCancelling(true);
    try {
      await cancelRun(runId);
      await loadData();
    } catch (err) {
      alert('Failed to cancel run: ' + (err.message || 'Unknown error'));
    } finally {
      setIsCancelling(false);
    }
  };

  const handleDownload = async () => {
    if (!runId || !statusData || isDownloading) return;
    setIsDownloading(true);
    try {
      const blob = await downloadRunZip(runId);
      const objectUrl = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = objectUrl;
      link.download = `fixsembly-repaired-${runId.slice(0, 8)}.zip`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
    } catch (err) {
      window.alert(err.message || 'Unable to download this repair archive.');
    } finally {
      setIsDownloading(false);
    }
  };

  const isTerminal = [
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
  ].includes(statusData?.status);

  const isSuccess = statusData?.status === 'passed' || statusData?.status === 'already_passing';
  const isFailed = statusData?.status === 'failed' || statusData?.status === 'error';
  const isRejected = statusData?.status === 'reviewer_rejected';

  // Fallback test output
  const testStdout =
    statusData?.test_stdout ||
    testResults?.stdout ||
    (statusData?.status === 'running'
      ? 'Fixsembly test runner initializing subprocess pytest execution in the uploaded project...\nRunning test collection...'
      : 'No test console output available.');

  const currentIter = statusData?.current_iteration || 1;
  const iterations = statusData?.iterations || [];
  const latestIteration = iterations[iterations.length - 1] || null;

  const diffData = statusData?.latest_diff || (latestIteration?.code_changes ? { diff: latestIteration.code_changes[0]?.patch } : null);
  const codeChange = latestIteration?.code_changes?.[0] || statusData?.code_change;
  const reviewResult = latestIteration?.review_result || statusData?.review_result;
  const archPlan = latestIteration?.architecture_plan || statusData?.architecture_plan;

  return (
    <div className="space-y-6">
      {/* Top Navigation & Status Bar */}
      <div className="flex flex-wrap items-center justify-between gap-4 pb-4 border-b border-slate-200 dark:border-slate-800">
        <div className="flex items-center gap-3">
          <Link
            to="/overview"
            className="p-1.5 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 text-slate-700 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-100 hover:border-slate-300 dark:hover:border-slate-700 shadow-sm transition"
            title="Back to Overview"
          >
            <ArrowLeft className="h-4 w-4" />
          </Link>

          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-lg font-bold text-slate-900 dark:text-slate-100 tracking-tight">
                Repair Studio
              </h2>
              <span className="font-mono text-xs text-brand-600 dark:text-brand-400 bg-brand-500/10 border border-brand-500/20 px-2 py-0.5 rounded-lg">
                RUN-{runId?.slice(0, 8)}
              </span>
            </div>
            <p className="text-xs text-slate-600 dark:text-slate-400 mt-0.5">
              Project: <span className="text-slate-900 dark:text-slate-200 font-medium">{statusData?.project_name || 'Loading...'}</span>
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
              className="flex items-center gap-1.5 text-xs font-semibold px-3.5 py-2 rounded-xl transition border border-rose-500/30 bg-rose-500/10 hover:bg-rose-500/20 text-rose-600 dark:text-rose-300 shadow-sm"
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
              : 'bg-slate-100 dark:bg-slate-900 border border-slate-200 dark:border-slate-800 text-slate-400 dark:text-slate-500 cursor-not-allowed opacity-60'
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
        <div className="rounded-2xl border border-emerald-500/30 bg-emerald-500/10 p-4 flex flex-wrap items-center justify-between gap-3 text-emerald-700 dark:text-emerald-300 text-xs animate-in fade-in shadow-sm">
          <div className="flex items-center gap-3">
            <div className="h-8 w-8 rounded-xl bg-emerald-500/20 border border-emerald-500/30 flex items-center justify-center text-emerald-600 dark:text-emerald-400 flex-shrink-0">
              <CheckCircle2 className="h-5 w-5" />
            </div>
            <div>
              <p className="font-bold text-emerald-800 dark:text-emerald-200 text-sm">
                Repair Completed & Verified: Red to Green!
              </p>
              <p className="text-emerald-700/80 dark:text-emerald-400/80">
                All Pytest assertions passed and the Reviewer Agent verified zero regression risk.
              </p>
            </div>
          </div>
          <button
            onClick={handleDownload}
            className="flex items-center gap-1.5 text-xs font-semibold px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white transition shadow-sm"
          >
            <Download className="h-3.5 w-3.5" />
            <span>Download Repaired Project</span>
          </button>
        </div>
      )}

      {isFailed && (
        <div className="rounded-2xl border border-rose-500/30 bg-rose-500/10 p-4 flex items-center gap-3 text-rose-700 dark:text-rose-300 text-xs animate-in fade-in shadow-sm">
          <div className="h-8 w-8 rounded-xl bg-rose-500/20 border border-rose-500/30 flex items-center justify-center text-rose-600 dark:text-rose-400 flex-shrink-0">
            <XCircle className="h-5 w-5" />
          </div>
          <div>
            <p className="font-bold text-rose-800 dark:text-rose-200 text-sm">
              Repair Failed to Converge
            </p>
            <p className="text-rose-700/80 dark:text-rose-400/80">
              Max iterations reached without achieving exit code 0 or reviewer approval.
            </p>
          </div>
        </div>
      )}

      {isRejected && (
        <div className="rounded-2xl border border-orange-500/30 bg-orange-500/10 p-4 flex items-center gap-3 text-orange-700 dark:text-orange-300 text-xs animate-in fade-in shadow-sm">
          <div className="h-8 w-8 rounded-xl bg-orange-500/20 border border-orange-500/30 flex items-center justify-center text-orange-600 dark:text-orange-400 flex-shrink-0">
            <AlertTriangle className="h-5 w-5" />
          </div>
          <div>
            <p className="font-bold text-orange-800 dark:text-orange-200 text-sm">
              Reviewer Audit Rejected Patch
            </p>
            <p className="text-orange-700/80 dark:text-orange-400/80">
              The patch caused side effects or regressions evaluated as high risk by the Reviewer Agent.
            </p>
          </div>
        </div>
      )}

      {statusData?.status === 'cancelled' && (
        <div className="rounded-2xl border border-slate-300 dark:border-slate-700 bg-slate-100 dark:bg-slate-900/60 p-4 flex items-center gap-3 text-slate-700 dark:text-slate-300 text-xs animate-in fade-in shadow-sm">
          <div className="h-8 w-8 rounded-xl bg-slate-200 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 flex items-center justify-center text-slate-500 dark:text-slate-400 flex-shrink-0">
            <XCircle className="h-5 w-5" />
          </div>
          <div>
            <p className="font-bold text-slate-800 dark:text-slate-200 text-sm">
              Repair Run Cancelled
            </p>
            <p className="text-slate-600 dark:text-slate-400">
              The repair process was terminated by user request.
            </p>
          </div>
        </div>
      )}

      {/* Multi-Agent Stepper Visualizer */}
      <AgentStepper statusData={statusData} />

      {/* Tab Navigation */}
      <div className="flex items-center gap-2 border-b border-slate-200 dark:border-slate-800/80 pb-px">
        <button
          onClick={() => setActiveTab('diff')}
          className={`flex items-center gap-2 px-4 py-2.5 text-xs font-medium border-b-2 transition ${activeTab === 'diff'
            ? 'border-brand-600 dark:border-brand-500 text-brand-600 dark:text-brand-300 font-semibold'
            : 'border-transparent text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200'
            }`}
        >
          <Code2 className="h-4 w-4" />
          <span>Synthesized Diffs</span>
        </button>

        <button
          onClick={() => setActiveTab('terminal')}
          className={`flex items-center gap-2 px-4 py-2.5 text-xs font-medium border-b-2 transition ${activeTab === 'terminal'
            ? 'border-brand-600 dark:border-brand-500 text-brand-600 dark:text-brand-300 font-semibold'
            : 'border-transparent text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200'
            }`}
        >
          <TerminalIcon className="h-4 w-4" />
          <span>Pytest Truth Terminal</span>
        </button>

        <button
          onClick={() => setActiveTab('review')}
          className={`flex items-center gap-2 px-4 py-2.5 text-xs font-medium border-b-2 transition ${activeTab === 'review'
            ? 'border-brand-600 dark:border-brand-500 text-brand-600 dark:text-brand-300 font-semibold'
            : 'border-transparent text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200'
            }`}
        >
          <ShieldCheck className="h-4 w-4" />
          <span>Reviewer Audit Gate</span>
        </button>

        <button
          onClick={() => setActiveTab('timeline')}
          className={`flex items-center gap-2 px-4 py-2.5 text-xs font-medium border-b-2 transition ${activeTab === 'timeline'
            ? 'border-brand-600 dark:border-brand-500 text-brand-600 dark:text-brand-300 font-semibold'
            : 'border-transparent text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200'
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
              <div className="rounded-2xl border border-slate-200 dark:border-slate-800/80 bg-white dark:bg-slate-900/60 p-4 text-xs shadow-sm">
                <div className="flex items-center gap-2 mb-2">
                  <Sparkles className="h-4 w-4 text-brand-600 dark:text-brand-400" />
                  <h4 className="font-semibold text-slate-900 dark:text-slate-200">Architect Agent Strategy</h4>
                </div>
                <p className="text-slate-700 dark:text-slate-300 leading-relaxed font-sans">{archPlan.summary}</p>
                {archPlan.relevant_files?.length > 0 && (
                  <div className="mt-2.5 pt-2 border-t border-slate-100 dark:border-slate-800/60 flex items-center gap-2 text-[11px] font-mono text-slate-600 dark:text-slate-400">
                    <span className="text-slate-500">Target Files:</span>
                    {archPlan.relevant_files.map((f, i) => (
                      <span key={i} className="px-1.5 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-brand-600 dark:text-brand-300 border border-slate-200 dark:border-slate-700">
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
          <div className="rounded-2xl border border-slate-200 dark:border-slate-800/80 bg-white dark:bg-slate-900/60 p-5 shadow-sm">
            <h4 className="text-xs font-semibold text-slate-700 dark:text-slate-200 uppercase tracking-wider font-mono mb-4">
              Agent Execution Log
            </h4>
            <div className="space-y-3 font-mono text-xs">
              {(statusData?.timeline || []).length === 0 ? (
                <p className="text-slate-500">Waiting for agent events...</p>
              ) : (
                statusData.timeline.map((ev, i) => (
                  <div
                    key={i}
                    className="flex items-start gap-3 p-2.5 rounded-xl border border-slate-100 dark:border-slate-800/60 bg-slate-50 dark:bg-slate-950/40"
                  >
                    <span className="text-slate-500 text-[10px] w-16 flex-shrink-0 pt-0.5">
                      {ev.time || `T+${i}s`}
                    </span>
                    <span className="px-2 py-0.5 rounded text-[10px] uppercase font-semibold bg-brand-500/10 text-brand-600 dark:text-brand-400 border border-brand-500/20">
                      {ev.agent}
                    </span>
                    <span className="text-slate-700 dark:text-slate-300 font-sans text-xs flex-1">
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

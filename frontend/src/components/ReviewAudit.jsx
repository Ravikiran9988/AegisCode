import { ShieldCheck, ShieldAlert, CheckCircle2, XCircle, AlertTriangle } from 'lucide-react';

export default function ReviewAudit({ reviewResult }) {
  if (!reviewResult) {
    return (
      <div className="rounded-2xl border border-slate-800/80 bg-slate-900/40 p-5 text-center text-slate-500">
        <ShieldCheck className="h-6 w-6 mx-auto mb-2 text-slate-600" />
        <p className="text-xs font-medium">Reviewer Audit Gate Pending</p>
        <p className="text-[11px] text-slate-500 mt-0.5">
          The Reviewer Agent evaluates code safety after Pytest passes successfully.
        </p>
      </div>
    );
  }

  const {
    approved = false,
    root_cause_fixed = false,
    regression_risk = 'low',
    feedback = '',
    explanation = '',
  } = reviewResult;

  const riskColor = {
    low: 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20',
    medium: 'text-amber-400 bg-amber-500/10 border-amber-500/20',
    high: 'text-rose-400 bg-rose-500/10 border-rose-500/20',
  }[regression_risk.toLowerCase()] || 'text-slate-400 bg-slate-800 border-slate-700';

  return (
    <div className="rounded-2xl border border-slate-800/80 bg-slate-900/70 p-5 backdrop-blur-sm">
      <div className="flex items-center justify-between pb-3 mb-4 border-b border-slate-800/80">
        <div className="flex items-center gap-2">
          {approved ? (
            <div className="h-7 w-7 rounded-lg bg-emerald-500/15 border border-emerald-500/30 flex items-center justify-center text-emerald-400">
              <ShieldCheck className="h-4 w-4" />
            </div>
          ) : (
            <div className="h-7 w-7 rounded-lg bg-rose-500/15 border border-rose-500/30 flex items-center justify-center text-rose-400">
              <ShieldAlert className="h-4 w-4" />
            </div>
          )}
          <div>
            <h4 className="text-xs font-semibold text-slate-100 uppercase tracking-wider font-mono">
              Reviewer Audit Gate
            </h4>
            <p className="text-[11px] text-slate-400">Independent safety & regression assessment</p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <span
            className={`text-xs font-semibold px-2.5 py-0.5 rounded-full border ${
              approved
                ? 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30'
                : 'bg-rose-500/15 text-rose-400 border-rose-500/30'
            }`}
          >
            {approved ? 'Approved ✓' : 'Rejected ✗'}
          </span>
        </div>
      </div>

      {/* Metrics Row */}
      <div className="grid grid-cols-2 gap-3 mb-4">
        <div className="rounded-xl border border-slate-800/80 bg-slate-950 p-3 flex items-center justify-between">
          <span className="text-xs text-slate-400">Root Cause Fixed</span>
          <span className="flex items-center gap-1.5 text-xs font-medium text-slate-200">
            {root_cause_fixed ? (
              <>
                <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" />
                <span>Yes</span>
              </>
            ) : (
              <>
                <XCircle className="h-3.5 w-3.5 text-rose-400" />
                <span>No</span>
              </>
            )}
          </span>
        </div>

        <div className="rounded-xl border border-slate-800/80 bg-slate-950 p-3 flex items-center justify-between">
          <span className="text-xs text-slate-400">Regression Risk</span>
          <span className={`text-[11px] font-mono uppercase px-2 py-0.5 rounded border font-semibold ${riskColor}`}>
            {regression_risk}
          </span>
        </div>
      </div>

      {/* Feedback Text */}
      {(feedback || explanation) && (
        <div className="rounded-xl border border-slate-800/80 bg-slate-950/60 p-3 text-xs leading-relaxed text-slate-300">
          <p className="text-[11px] font-mono text-slate-500 uppercase tracking-wider mb-1">Audit Rationale</p>
          <p className="whitespace-pre-wrap">{feedback || explanation}</p>
        </div>
      )}
    </div>
  );
}

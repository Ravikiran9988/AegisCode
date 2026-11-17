import { CheckCircle2, Clock, XCircle, Loader2, Sparkles, Code2, FlaskConical, ShieldCheck, AlertTriangle } from 'lucide-react';

export default function AgentStepper({ statusData }) {
  if (!statusData) {
    return (
      <div className="flex items-center justify-center p-8 text-slate-500">
        <Loader2 className="h-5 w-5 animate-spin mr-2" />
        <span>Loading execution graph...</span>
      </div>
    );
  }

  const { pipeline_nodes = {}, current_node = '', status = 'running', current_iteration = 1, max_iterations = 5 } = statusData;

  const steps = [
    {
      id: 'initial_test',
      name: 'Baseline Pytest',
      role: 'Test Suite Assessment',
      icon: FlaskConical,
      state: pipeline_nodes.initial_test || (current_node === 'initial_test' ? 'running' : 'pending'),
    },
    {
      id: 'architect',
      name: 'Architect Agent',
      role: 'Root Cause & Plan',
      icon: Sparkles,
      state: pipeline_nodes.architect || (current_node === 'architect' ? 'running' : 'pending'),
    },
    {
      id: 'coder',
      name: 'Coder Agent',
      role: 'Synthesizing Patch',
      icon: Code2,
      state: pipeline_nodes.coder || (current_node === 'coder' ? 'running' : 'pending'),
    },
    {
      id: 'pytest',
      name: 'Pytest Verification',
      role: 'Execution Truth',
      icon: FlaskConical,
      state: pipeline_nodes.pytest || (current_node === 'test' ? 'running' : 'pending'),
    },
    {
      id: 'reviewer',
      name: 'Reviewer Agent',
      role: 'Audit & Safety Gate',
      icon: ShieldCheck,
      state: pipeline_nodes.reviewer || (current_node === 'reviewer' ? 'running' : 'pending'),
    },
  ];

  function getStepStyle(state) {
    switch (state) {
      case 'completed':
        return {
          badge: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30',
          indicator: 'bg-emerald-500 text-white',
          line: 'bg-emerald-500',
          icon: CheckCircle2,
        };
      case 'running':
        return {
          badge: 'bg-brand-500/15 text-brand-300 border-brand-500/40 ring-2 ring-brand-500/20 shadow-lg shadow-brand-500/10',
          indicator: 'bg-brand-500 text-white animate-pulse',
          line: 'bg-slate-700',
          icon: Loader2,
        };
      case 'failed':
        return {
          badge: 'bg-rose-500/15 text-rose-400 border-rose-500/30',
          indicator: 'bg-rose-500 text-white',
          line: 'bg-slate-700',
          icon: XCircle,
        };
      case 'skipped':
        return {
          badge: 'bg-slate-800/40 text-slate-500 border-slate-800',
          indicator: 'bg-slate-700 text-slate-400',
          line: 'bg-slate-800',
          icon: Clock,
        };
      default:
        return {
          badge: 'bg-slate-900/60 text-slate-400 border-slate-800/80',
          indicator: 'bg-slate-800 text-slate-400',
          line: 'bg-slate-800',
          icon: Clock,
        };
    }
  }

  return (
    <div className="w-full bg-slate-900/70 border border-slate-800/80 rounded-2xl p-5 backdrop-blur-sm">
      {/* Header with Iteration Badge */}
      <div className="flex flex-wrap items-center justify-between gap-3 mb-6 pb-4 border-b border-slate-800/80">
        <div className="flex items-center gap-2.5">
          <div className="h-8 w-8 rounded-lg bg-brand-500/10 border border-brand-500/20 flex items-center justify-center text-brand-400">
            <Sparkles className="h-4 w-4" />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-slate-100 tracking-tight">
              Self-Healing Multi-Agent Pipeline
            </h3>
            <p className="text-xs text-slate-400">
              Coordinated autonomous execution with authoritative Pytest gate
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <span className="text-xs font-mono px-3 py-1 rounded-full bg-slate-800 border border-slate-700 text-slate-300">
            Iteration <span className="text-brand-400 font-semibold">{current_iteration}</span> of {max_iterations}
          </span>
          <span
            className={`text-xs font-semibold uppercase tracking-wider px-2.5 py-1 rounded-full border ${
              status === 'passed' || status === 'already_passing'
                ? 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30'
                : status === 'failed' || status === 'error'
                ? 'bg-rose-500/15 text-rose-400 border-rose-500/30'
                : status === 'stalled'
                ? 'bg-amber-500/15 text-amber-400 border-amber-500/30'
                : 'bg-brand-500/15 text-brand-300 border-brand-500/30 animate-pulse'
            }`}
          >
            {status}
          </span>
        </div>
      </div>

      {/* Stepper Graph Grid */}
      <div className="grid grid-cols-1 md:grid-cols-5 gap-3 relative">
        {steps.map((step, idx) => {
          const style = getStepStyle(step.state);
          const IconComponent = step.state === 'running' ? Loader2 : style.icon;
          const isCurrent = step.state === 'running';

          return (
            <div
              key={step.id}
              className={`flex flex-col p-3.5 rounded-xl border transition-all duration-300 relative ${style.badge}`}
            >
              <div className="flex items-center justify-between mb-2">
                <div className={`h-7 w-7 rounded-lg flex items-center justify-center ${style.indicator}`}>
                  <step.icon className="h-3.5 w-3.5" />
                </div>
                <span className="text-[10px] font-mono font-medium uppercase tracking-wider text-slate-400">
                  Step 0{idx + 1}
                </span>
              </div>

              <div className="mt-1">
                <p className="text-xs font-semibold text-slate-100 flex items-center gap-1.5">
                  {step.name}
                  {isCurrent && <span className="h-1.5 w-1.5 rounded-full bg-brand-400 animate-ping" />}
                </p>
                <p className="text-[11px] text-slate-400 mt-0.5 leading-snug">{step.role}</p>
              </div>

              <div className="mt-3 pt-2 border-t border-slate-800/60 flex items-center justify-between text-[10px] font-mono">
                <span className="text-slate-500">Status:</span>
                <span className="font-semibold capitalize">{step.state}</span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

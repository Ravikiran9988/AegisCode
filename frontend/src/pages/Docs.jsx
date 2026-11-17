import { BookOpen, ShieldCheck, Sparkles, Code2, FlaskConical, Cpu, Lock, CheckCircle2 } from 'lucide-react';

export default function Docs() {
  return (
    <div className="max-w-4xl mx-auto space-y-8 py-2">
      {/* Header */}
      <div className="pb-4 border-b border-slate-800">
        <h2 className="text-xl font-bold tracking-tight text-white flex items-center gap-2">
          <BookOpen className="h-5 w-5 text-brand-400" />
          <span>Fixsembly Architecture & Documentation</span>
        </h2>
        <p className="text-xs text-slate-400 mt-1">
          Three Agents. One Verified Fix. Red to green, automatically.
        </p>
      </div>

      {/* Overview section */}
      <section className="space-y-3">
        <h3 className="text-base font-bold text-slate-100 flex items-center gap-2">
          <Cpu className="h-4 w-4 text-brand-400" />
          <span>Autonomous Repair Lifecycle</span>
        </h3>
        <p className="text-xs text-slate-300 leading-relaxed">
          Fixsembly is a self-healing multi-agent software engineering system that analyzes failing Python projects, isolates bugs, generates surgical code patches, executes tests, and verifies fixes with zero human intervention.
        </p>

        <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-5 font-mono text-xs text-slate-300 space-y-2">
          <div className="text-brand-400 font-semibold">[Complete Repair Lifecycle]</div>
          <p className="text-slate-400">
            Upload Project → Initial Pytest → Architect Analysis → Coder Repair → Pytest Verification → Reviewer Audit → Final Result (.ZIP)
          </p>
        </div>
      </section>

      {/* Agents Breakdown */}
      <section className="space-y-4">
        <h3 className="text-base font-bold text-slate-100">The Three Autonomous Agents</h3>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="p-4 rounded-xl border border-slate-800 bg-slate-900/40">
            <div className="h-8 w-8 rounded-lg bg-blue-500/10 text-blue-400 flex items-center justify-center mb-3">
              <Sparkles className="h-4 w-4" />
            </div>
            <h4 className="text-sm font-semibold text-slate-100">Architect Agent</h4>
            <p className="text-xs text-slate-400 mt-1 leading-relaxed">
              Read-only agent that parses pytest failure tracebacks and file tree structures to produce a strongly-typed <code className="text-blue-300">ArchitecturePlan</code> with root causes and relevant target files.
            </p>
          </div>

          <div className="p-4 rounded-xl border border-slate-800 bg-slate-900/40">
            <div className="h-8 w-8 rounded-lg bg-indigo-500/10 text-indigo-400 flex items-center justify-center mb-3">
              <Code2 className="h-4 w-4" />
            </div>
            <h4 className="text-sm font-semibold text-slate-100">Coder Agent</h4>
            <p className="text-xs text-slate-400 mt-1 leading-relaxed">
              Synthesizes precise unified diff patches or targeted file writes. Enforces strict file modification policies and includes an automated recovery fallback for malformed diffs.
            </p>
          </div>

          <div className="p-4 rounded-xl border border-slate-800 bg-slate-900/40">
            <div className="h-8 w-8 rounded-lg bg-emerald-500/10 text-emerald-400 flex items-center justify-center mb-3">
              <ShieldCheck className="h-4 w-4" />
            </div>
            <h4 className="text-sm font-semibold text-slate-100">Reviewer Agent</h4>
            <p className="text-xs text-slate-400 mt-1 leading-relaxed">
              Independent audit agent that evaluates git diffs and test results to verify that root causes are resolved without introducing regression risks or unexpected side effects.
            </p>
          </div>
        </div>
      </section>

      {/* Pytest As Truth Gate */}
      <section className="space-y-3">
        <h3 className="text-base font-bold text-slate-100 flex items-center gap-2">
          <FlaskConical className="h-4 w-4 text-amber-400" />
          <span>Pytest As The Source of Truth</span>
        </h3>
        <p className="text-xs text-slate-300 leading-relaxed">
          In Fixsembly, LLMs are never asked to evaluate whether tests passed. Only the actual exit code returned by the Pytest execution subprocess serves as the pass/fail signal:
        </p>
        <ul className="list-disc list-inside text-xs text-slate-400 space-y-1 font-mono">
          <li>Exit Code 0: All tests passed (Success)</li>
          <li>Exit Code 1: Some tests failed (Route to retry)</li>
          <li>Exit Code 2: Execution interrupted</li>
          <li>Exit Code 3/4: Internal or CLI usage error</li>
        </ul>
      </section>

      {/* Security Policies */}
      <section className="space-y-3">
        <h3 className="text-base font-bold text-slate-100 flex items-center gap-2">
          <Lock className="h-4 w-4 text-rose-400" />
          <span>Security & Policy Enforcement</span>
        </h3>
        <div className="rounded-2xl border border-slate-800 bg-slate-900/40 p-4 text-xs text-slate-300 space-y-2">
          <p className="flex items-center gap-2 text-emerald-400 font-semibold">
            <CheckCircle2 className="h-3.5 w-3.5" /> Test File Immutability
          </p>
          <p className="text-slate-400">
            The Coder Agent is strictly prohibited from modifying test files (e.g., <code className="text-slate-300">test_*.py</code>, <code className="text-slate-300">*_test.py</code>). This prevents agents from deleting assertions to manufacture false passing runs.
          </p>
          <p className="flex items-center gap-2 text-emerald-400 font-semibold mt-3">
            <CheckCircle2 className="h-3.5 w-3.5" /> Directory Traversal Defenses
          </p>
          <p className="text-slate-400">
            All file reads and patch writes are strictly resolved against the temporary workspace root path. Attempts to escape via relative paths are rejected at tool execution time.
          </p>
        </div>
      </section>
    </div>
  );
}

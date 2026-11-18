import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  ShieldCheck,
  Sparkles,
  Code2,
  FlaskConical,
  ArrowRight,
  CheckCircle2,
  Terminal,
  Zap,
  Cpu,
  Play,
  Layers,
  ChevronRight,
  GitCommit,
  Check,
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { FixsemblyIcon } from '../assets/logo';

export default function Landing({ onOpenAuthModal }) {
  const { user, isGuest, enterAsGuest } = useAuth();
  const navigate = useNavigate();
  const [quickName, setQuickName] = useState('');
  const [activeTab, setActiveTab] = useState('pipeline'); // 'pipeline' | 'diff'

  const handleQuickStart = async (e) => {
    e?.preventDefault();
    if (!user && !isGuest) {
      await enterAsGuest(quickName || 'Guest Engineer');
    }
    navigate('/repair/new');
  };

  const handleLaunchDemo = async (demoName = 'calculator') => {
    if (!user && !isGuest) {
      await enterAsGuest('Guest Engineer');
    }
    navigate('/repair/new');
  };

  return (
    <div className="relative pt-2 pb-16 sm:pt-4 sm:pb-20 overflow-hidden">
      {/* Background Radial Glow & Engineering Grid */}
      <div className="absolute inset-0 bg-[radial-gradient(#1e293b_1px,transparent_1px)] [background-size:24px_24px] opacity-40 pointer-events-none" />
      <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[700px] h-[300px] bg-gradient-to-b from-brand-500/15 via-indigo-500/5 to-transparent blur-[100px] rounded-full pointer-events-none -z-10" />

      <div className="relative max-w-5xl mx-auto px-4 sm:px-6 text-center">
        {/* Top Announcement Pill */}
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-slate-900/90 border border-slate-800/80 shadow-inner mb-4 hover:border-brand-500/30 transition cursor-default">
          <span className="flex h-1.5 w-1.5 rounded-full bg-brand-400 animate-pulse" />
          <span className="text-[11px] font-mono font-medium text-slate-300">
            Fixsembly V2.0 • Autonomous Multi-Agent Repair
          </span>
          <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-brand-500/10 text-brand-400 border border-brand-500/20">
            NEW
          </span>
        </div>

        {/* Hero Title with Tight Balanced Spacing */}
        <h1 className="text-4xl sm:text-6xl font-black tracking-tight text-white mb-3 leading-[1.1]">
          Three Agents.{' '}
          <span className="bg-gradient-to-r from-brand-400 via-indigo-300 to-emerald-400 bg-clip-text text-transparent">
            One Verified Fix.
          </span>
        </h1>

        {/* Tagline / Subtitle */}
        <p className="max-w-2xl mx-auto text-sm sm:text-base text-slate-300 mb-6 leading-relaxed font-normal">
          Autonomous software engineering system that diagnoses failing Python projects,
          synthesizes targeted unified patches, runs real Pytest assertions, and verifies zero regressions —{' '}
          <span className="text-emerald-400 font-semibold underline decoration-emerald-500/40 underline-offset-2">
            red to green, automatically
          </span>
          .
        </p>

        {/* Quick Launch CTA Form */}
        <div className="max-w-md mx-auto mb-6">
          <form
            onSubmit={handleQuickStart}
            className="flex flex-col sm:flex-row items-center gap-2 bg-slate-900/90 border border-slate-700/60 p-1.5 rounded-2xl shadow-xl shadow-slate-950/80 backdrop-blur-md focus-within:border-brand-500/60 transition"
          >
            <input
              type="text"
              placeholder={user ? user.nickname || user.email : isGuest ? 'Logged in as Guest' : 'Enter your name or team (e.g. Ravi)...'}
              disabled={!!user || isGuest}
              value={user ? user.nickname || user.email : isGuest ? 'Guest Access Active' : quickName}
              onChange={(e) => setQuickName(e.target.value)}
              className="w-full bg-transparent px-3.5 py-2 text-xs text-slate-100 placeholder-slate-500 focus:outline-none disabled:opacity-75 font-sans"
            />
            <button
              type="submit"
              className="w-full sm:w-auto flex-shrink-0 flex items-center justify-center gap-2 bg-gradient-to-r from-brand-600 to-indigo-600 hover:from-brand-500 hover:to-indigo-500 text-white font-semibold px-4 py-2 rounded-xl text-xs shadow-md shadow-brand-500/25 transition active:scale-[0.98]"
            >
              <span>Launch Studio</span>
              <ArrowRight className="h-3.5 w-3.5" />
            </button>
          </form>

          {/* Instant Demo Quick-start Chips */}
          <div className="flex flex-wrap items-center justify-center gap-2 mt-3 text-[11px] text-slate-400">
            <span className="text-slate-500">Or explore instant demos:</span>
            <button
              type="button"
              onClick={() => handleLaunchDemo('calculator')}
              className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-lg bg-slate-900/80 hover:bg-slate-800 text-slate-300 border border-slate-800 hover:border-slate-700 transition"
            >
              <Play className="h-2.5 w-2.5 text-brand-400" />
              <span>Buggy Calculator</span>
            </button>
            <button
              type="button"
              onClick={() => handleLaunchDemo('fastapi')}
              className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-lg bg-slate-900/80 hover:bg-slate-800 text-slate-300 border border-slate-800 hover:border-slate-700 transition"
            >
              <Play className="h-2.5 w-2.5 text-emerald-400" />
              <span>Async API</span>
            </button>
          </div>
        </div>

        {/* Live Visual Pipeline Mock Card */}
        <div className="max-w-3xl mx-auto rounded-2xl border border-slate-800/80 bg-slate-900/60 p-4 shadow-2xl backdrop-blur-md mb-10 text-left">
          <div className="flex items-center justify-between pb-3 mb-3 border-b border-slate-800/80">
            <div className="flex items-center gap-2">
              <span className="h-2.5 w-2.5 rounded-full bg-rose-500/80" />
              <span className="h-2.5 w-2.5 rounded-full bg-amber-500/80" />
              <span className="h-2.5 w-2.5 rounded-full bg-emerald-500/80" />
              <span className="ml-2 font-mono text-[11px] text-slate-400">fixsembly-repair-pipeline.py</span>
            </div>
            <div className="flex items-center gap-1.5 text-[10px] font-mono text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 px-2 py-0.5 rounded-md">
              <Check className="h-3 w-3" /> VERIFIED FIX (Pytest 0)
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <div className="p-3 rounded-xl bg-slate-950/60 border border-slate-800/60">
              <div className="flex items-center gap-1.5 text-blue-400 text-xs font-semibold mb-1">
                <Sparkles className="h-3.5 w-3.5" />
                <span>1. Architect</span>
              </div>
              <p className="text-[11px] text-slate-400 leading-tight">
                Pinpointed root cause in <code className="text-slate-300">calculator.py:14</code> (operator precedence bug).
              </p>
            </div>

            <div className="p-3 rounded-xl bg-slate-950/60 border border-slate-800/60">
              <div className="flex items-center gap-1.5 text-indigo-400 text-xs font-semibold mb-1">
                <Code2 className="h-3.5 w-3.5" />
                <span>2. Coder</span>
              </div>
              <p className="text-[11px] text-slate-400 leading-tight">
                Synthesized 4-line surgical patch; test suite left strictly immutable.
              </p>
            </div>

            <div className="p-3 rounded-xl bg-slate-950/60 border border-slate-800/60">
              <div className="flex items-center gap-1.5 text-emerald-400 text-xs font-semibold mb-1">
                <ShieldCheck className="h-3.5 w-3.5" />
                <span>3. Reviewer</span>
              </div>
              <p className="text-[11px] text-slate-400 leading-tight">
                Pytest exit code: 0. Zero regression risk detected. Approved.
              </p>
            </div>
          </div>
        </div>

        {/* 3 Agents Architecture Cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-left mb-10">
          {/* Architect */}
          <div className="p-5 rounded-2xl border border-slate-800/80 bg-slate-900/40 backdrop-blur-sm relative overflow-hidden group hover:border-blue-500/40 transition">
            <div className="h-9 w-9 rounded-xl bg-blue-500/10 border border-blue-500/20 text-blue-400 flex items-center justify-center mb-3">
              <Sparkles className="h-4 w-4" />
            </div>
            <h3 className="text-sm font-bold text-slate-100 mb-1">Architect Agent</h3>
            <p className="text-xs text-slate-400 leading-relaxed">
              Analyzes Pytest stack traces, failure diagnostics, and workspace structure to draft an exact repair strategy.
            </p>
            <div className="mt-3 pt-2.5 border-t border-slate-800/60 flex items-center gap-1.5 text-[11px] font-mono text-blue-400">
              <CheckCircle2 className="h-3 w-3" /> Root cause isolation
            </div>
          </div>

          {/* Coder */}
          <div className="p-5 rounded-2xl border border-slate-800/80 bg-slate-900/40 backdrop-blur-sm relative overflow-hidden group hover:border-indigo-500/40 transition">
            <div className="h-9 w-9 rounded-xl bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 flex items-center justify-center mb-3">
              <Code2 className="h-4 w-4" />
            </div>
            <h3 className="text-sm font-bold text-slate-100 mb-1">Coder Agent</h3>
            <p className="text-xs text-slate-400 leading-relaxed">
              Synthesizes precise unified diff patches strictly bounded by anti-tamper test protection rules.
            </p>
            <div className="mt-3 pt-2.5 border-t border-slate-800/60 flex items-center gap-1.5 text-[11px] font-mono text-indigo-400">
              <CheckCircle2 className="h-3 w-3" /> Safe diff synthesis
            </div>
          </div>

          {/* Reviewer */}
          <div className="p-5 rounded-2xl border border-slate-800/80 bg-slate-900/40 backdrop-blur-sm relative overflow-hidden group hover:border-emerald-500/40 transition">
            <div className="h-9 w-9 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 flex items-center justify-center mb-3">
              <ShieldCheck className="h-4 w-4" />
            </div>
            <h3 className="text-sm font-bold text-slate-100 mb-1">Reviewer Agent</h3>
            <p className="text-xs text-slate-400 leading-relaxed">
              Audits patches against subprocess Pytest execution to guarantee zero false positives and verify regression safety.
            </p>
            <div className="mt-3 pt-2.5 border-t border-slate-800/60 flex items-center gap-1.5 text-[11px] font-mono text-emerald-400">
              <CheckCircle2 className="h-3 w-3" /> Authoritative quality gate
            </div>
          </div>
        </div>

        {/* Feature Highlights Grid */}
        <div className="rounded-2xl border border-slate-800/80 bg-slate-900/30 p-6 text-left">
          <div className="flex items-center gap-2 mb-4">
            <Zap className="h-4 w-4 text-brand-400" />
            <h3 className="text-sm font-bold text-slate-100 uppercase tracking-wider font-mono">
              Engineered for Verification Truth
            </h3>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 text-xs text-slate-400">
            <div>
              <p className="font-semibold text-slate-200 mb-1 flex items-center gap-1.5">
                <FlaskConical className="h-3.5 w-3.5 text-amber-400" /> Pytest As Truth
              </p>
              <p className="leading-relaxed">
                The LLM never hallucinates test success. Real OS subprocess exit codes provide the ground truth.
              </p>
            </div>

            <div>
              <p className="font-semibold text-slate-200 mb-1 flex items-center gap-1.5">
                <Cpu className="h-3.5 w-3.5 text-blue-400" /> LangGraph Coordinator
              </p>
              <p className="leading-relaxed">
                Autonomous state machine routes patch failures, manages retries, and avoids costly duplicate analysis.
              </p>
            </div>

            <div>
              <p className="font-semibold text-slate-200 mb-1 flex items-center gap-1.5">
                <Terminal className="h-3.5 w-3.5 text-emerald-400" /> Real-Time SSE Stream
              </p>
              <p className="leading-relaxed">
                Telemetry streams agent thoughts, live Pytest output, and Monaco diffs with zero page refreshes.
              </p>
            </div>

            <div>
              <p className="font-semibold text-slate-200 mb-1 flex items-center gap-1.5">
                <ShieldCheck className="h-3.5 w-3.5 text-rose-400" /> Anti-Tamper Security
              </p>
              <p className="leading-relaxed">
                Policy controls strictly prevent LLMs from tampering with unit tests, CI configs, or secret keys.
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

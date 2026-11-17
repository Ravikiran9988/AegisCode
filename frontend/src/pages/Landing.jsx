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
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { FixsemblyIcon } from '../assets/logo';

export default function Landing({ onOpenAuthModal }) {
  const { user, isGuest, enterAsGuest } = useAuth();
  const navigate = useNavigate();
  const [quickName, setQuickName] = useState('');

  const handleQuickStart = async (e) => {
    e.preventDefault();
    if (!user && !isGuest) {
      await enterAsGuest(quickName || 'Guest Engineer');
    }
    navigate('/repair/new');
  };

  return (
    <div className="relative overflow-hidden py-12 md:py-20">
      {/* Glow gradient background */}
      <div className="absolute top-1/4 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[350px] bg-brand-500/10 blur-[120px] rounded-full pointer-events-none -z-10" />

      <div className="max-w-5xl mx-auto px-4 sm:px-6 text-center">
        {/* Brand Icon Convergence */}
        <div className="flex justify-center mb-5">
          <div className="p-3 rounded-2xl bg-slate-900/90 border border-slate-800 shadow-xl shadow-brand-500/10">
            <FixsemblyIcon size={44} />
          </div>
        </div>

        {/* Badge */}
        <div className="inline-flex items-center gap-2 px-3.5 py-1 rounded-full bg-brand-500/10 border border-brand-500/20 text-brand-300 text-xs font-mono font-medium mb-6 animate-in fade-in">
          <span>Self-Healing Multi-Agent Software Engineering System</span>
        </div>

        {/* Hero Title */}
        <h1 className="text-4xl sm:text-6xl font-extrabold tracking-tight text-white mb-6 leading-tight">
          Three Agents. <br className="hidden sm:inline" />
          <span className="bg-gradient-to-r from-brand-400 via-indigo-300 to-emerald-400 bg-clip-text text-transparent">
            One Verified Fix.
          </span>
        </h1>

        {/* Tagline / Subtitle */}
        <p className="max-w-2xl mx-auto text-base sm:text-lg text-slate-300 mb-8 leading-relaxed">
          Upload a failing Python project. Fixsembly autonomously analyzes root causes, synthesizes targeted patches, executes Pytest, and audits regressions until your test suite turns{' '}
          <span className="text-emerald-400 font-semibold underline decoration-emerald-500/50">
            red to green, automatically
          </span>
          .
        </p>

        {/* Quick Launch CTA Form */}
        <div className="max-w-md mx-auto mb-16">
          <form
            onSubmit={handleQuickStart}
            className="flex flex-col sm:flex-row items-center gap-2 bg-slate-900/90 border border-slate-800 p-1.5 rounded-2xl shadow-2xl backdrop-blur-md"
          >
            <input
              type="text"
              placeholder={user ? user.nickname || user.email : isGuest ? 'Logged in as Guest' : 'Enter your name for instant access...'}
              disabled={!!user || isGuest}
              value={user ? user.nickname || user.email : isGuest ? 'Guest Access Active' : quickName}
              onChange={(e) => setQuickName(e.target.value)}
              className="w-full bg-transparent px-4 py-2.5 text-xs text-slate-100 placeholder-slate-500 focus:outline-none disabled:opacity-75"
            />
            <button
              type="submit"
              className="w-full sm:w-auto flex-shrink-0 flex items-center justify-center gap-2 bg-gradient-to-r from-brand-600 to-indigo-600 hover:from-brand-500 hover:to-indigo-500 text-white font-semibold px-5 py-2.5 rounded-xl text-xs shadow-lg shadow-brand-500/25 transition"
            >
              <span>Launch Studio</span>
              <ArrowRight className="h-3.5 w-3.5" />
            </button>
          </form>

          <p className="text-[11px] text-slate-500 mt-2 font-mono">
            No credit card required. Works with local Ollama or hosted Groq models.
          </p>
        </div>

        {/* 3 Agents Architecture Cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-5 text-left mb-16">
          {/* Architect */}
          <div className="p-6 rounded-2xl border border-slate-800/80 bg-slate-900/40 backdrop-blur-sm relative overflow-hidden group hover:border-blue-500/40 transition">
            <div className="h-10 w-10 rounded-xl bg-blue-500/10 border border-blue-500/20 text-blue-400 flex items-center justify-center mb-4">
              <Sparkles className="h-5 w-5" />
            </div>
            <h3 className="text-base font-bold text-slate-100 mb-1">Architect Agent</h3>
            <p className="text-xs text-slate-400 leading-relaxed">
              Inspects failing test diagnostics, call-stacks, and workspace structure to isolate the bug and draft a structured repair plan.
            </p>
            <div className="mt-4 pt-3 border-t border-slate-800/60 flex items-center gap-1.5 text-[11px] font-mono text-blue-400">
              <CheckCircle2 className="h-3 w-3" /> Root cause isolation
            </div>
          </div>

          {/* Coder */}
          <div className="p-6 rounded-2xl border border-slate-800/80 bg-slate-900/40 backdrop-blur-sm relative overflow-hidden group hover:border-indigo-500/40 transition">
            <div className="h-10 w-10 rounded-xl bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 flex items-center justify-center mb-4">
              <Code2 className="h-5 w-5" />
            </div>
            <h3 className="text-base font-bold text-slate-100 mb-1">Coder Agent</h3>
            <p className="text-xs text-slate-400 leading-relaxed">
              Synthesizes precise unified diff patches and applies modifications strictly bounded by test file immutability security policies.
            </p>
            <div className="mt-4 pt-3 border-t border-slate-800/60 flex items-center gap-1.5 text-[11px] font-mono text-indigo-400">
              <CheckCircle2 className="h-3 w-3" /> Safe diff synthesis
            </div>
          </div>

          {/* Reviewer */}
          <div className="p-6 rounded-2xl border border-slate-800/80 bg-slate-900/40 backdrop-blur-sm relative overflow-hidden group hover:border-emerald-500/40 transition">
            <div className="h-10 w-10 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 flex items-center justify-center mb-4">
              <ShieldCheck className="h-5 w-5" />
            </div>
            <h3 className="text-base font-bold text-slate-100 mb-1">Reviewer Agent</h3>
            <p className="text-xs text-slate-400 leading-relaxed">
              Independently audits generated diffs against authoritative Pytest results to verify root-cause resolution and eliminate regression risk.
            </p>
            <div className="mt-4 pt-3 border-t border-slate-800/60 flex items-center gap-1.5 text-[11px] font-mono text-emerald-400">
              <CheckCircle2 className="h-3 w-3" /> Authoritative quality gate
            </div>
          </div>
        </div>

        {/* Feature Highlights Grid */}
        <div className="rounded-3xl border border-slate-800/80 bg-slate-900/30 p-8 text-left">
          <div className="flex items-center gap-2 mb-6">
            <Zap className="h-5 w-5 text-brand-400" />
            <h3 className="text-lg font-bold text-slate-100">Engineered for Verification Truth</h3>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6 text-xs text-slate-400">
            <div>
              <p className="font-semibold text-slate-200 mb-1 flex items-center gap-1.5">
                <FlaskConical className="h-3.5 w-3.5 text-amber-400" /> Pytest As Truth
              </p>
              <p className="leading-relaxed">
                The LLM never decides whether tests pass. Actual subprocess Pytest exit codes provide the authoritative signal.
              </p>
            </div>

            <div>
              <p className="font-semibold text-slate-200 mb-1 flex items-center gap-1.5">
                <Cpu className="h-3.5 w-3.5 text-blue-400" /> LangGraph Coordinator
              </p>
              <p className="leading-relaxed">
                State machine orchestration routes patch failures, retries failed steps, and detects repeated loops automatically.
              </p>
            </div>

            <div>
              <p className="font-semibold text-slate-200 mb-1 flex items-center gap-1.5">
                <Terminal className="h-3.5 w-3.5 text-emerald-400" /> Live SSE Observability
              </p>
              <p className="leading-relaxed">
                Stream real-time agent thoughts, Pytest stdout/stderr, and synthesized diffs with zero page refreshing.
              </p>
            </div>

            <div>
              <p className="font-semibold text-slate-200 mb-1 flex items-center gap-1.5">
                <ShieldCheck className="h-3.5 w-3.5 text-rose-400" /> Anti-Tamper Policies
              </p>
              <p className="leading-relaxed">
                Security policies prevent agents from modifying test files or breaking workspace boundaries.
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

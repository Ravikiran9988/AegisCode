import { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
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
  FileCode2,
  UploadCloud,
  FileCheck,
  History,
  ExternalLink,
  BookOpen,
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { FixsemblyIcon } from '../assets/logo';

export default function Landing({ onOpenAuthModal }) {
  const { user, isGuest, enterAsGuest } = useAuth();
  const navigate = useNavigate();
  const [quickName, setQuickName] = useState('');
  const [activeTab, setActiveTab] = useState('diff'); // 'diff' | 'terminal' | 'flow'

  const handleQuickStart = async (e) => {
    e?.preventDefault();
    if (!user && !isGuest) {
      await enterAsGuest(quickName.trim() || 'Guest Engineer');
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
    <div className="relative pt-1 sm:pt-3 pb-16 overflow-hidden">
      {/* Background Engineering Canvas & Radial Glow */}
      <div className="absolute inset-0 bg-[radial-gradient(#cbd5e1_1px,transparent_1px)] dark:bg-[radial-gradient(#1e293b_1px,transparent_1px)] [background-size:24px_24px] opacity-40 dark:opacity-35 pointer-events-none" />
      <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[720px] h-[280px] bg-gradient-to-b from-brand-500/15 via-indigo-500/5 to-transparent blur-[90px] rounded-full pointer-events-none -z-10" />

      <div className="relative max-w-6xl mx-auto px-4 sm:px-6">
        {/* =========================================================
            HERO SECTION: Tight vertical rhythm, high-impact branding
           ========================================================= */}
        <div className="text-center max-w-3xl mx-auto pt-2 pb-6 sm:pt-4 sm:pb-8">
          {/* Top Pill Announcement */}
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-white dark:bg-slate-900/90 border border-slate-200 dark:border-slate-800 text-slate-700 dark:text-slate-300 text-xs font-mono mb-4 shadow-sm backdrop-blur-md">
            <span className="flex h-1.5 w-1.5 rounded-full bg-emerald-500 dark:bg-emerald-400 animate-pulse" />
            <span className="font-medium text-slate-800 dark:text-slate-200">Fixsembly</span>
            <span className="text-slate-400 dark:text-slate-600">•</span>
            <span className="text-slate-600 dark:text-slate-400 hidden sm:inline">Self-Healing Multi-Agent Engineering</span>
            <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-brand-500/10 text-brand-600 dark:text-brand-400 border border-brand-500/20 font-semibold">
              AUTONOMOUS
            </span>
          </div>

          {/* Primary Display Title */}
          <h1 className="text-4xl sm:text-6xl font-black tracking-tight text-slate-900 dark:text-slate-100 mb-3.5 leading-[1.1]">
            Three Agents.{' '}
            <span className="bg-gradient-to-r from-brand-600 via-indigo-600 to-emerald-600 dark:from-brand-400 dark:via-indigo-300 dark:to-emerald-400 bg-clip-text text-transparent">
              One Verified Fix.
            </span>
          </h1>

          {/* Subtitle Value Proposition */}
          <p className="text-sm sm:text-base text-slate-600 dark:text-slate-300 mb-6 leading-relaxed max-w-2xl mx-auto font-normal">
            Autonomous software engineering system that analyzes failing Python repositories,
            synthesizes targeted unified patches, runs real Pytest assertions, and verifies zero regressions, taking code{' '}
            <span className="text-emerald-600 dark:text-emerald-400 font-semibold underline decoration-emerald-500/40 underline-offset-2">
              red to green, automatically
            </span>
            .
          </p>

          {/* Quick Launch Console Form */}
          <div className="max-w-md mx-auto mb-4">
            <form
              onSubmit={handleQuickStart}
              className="flex flex-col sm:flex-row items-stretch sm:items-center gap-2 bg-white dark:bg-slate-900/95 border border-slate-300 dark:border-slate-700/80 p-1.5 rounded-2xl shadow-lg dark:shadow-xl dark:shadow-slate-950/80 backdrop-blur-md focus-within:border-brand-500 transition"
            >
              <div className="flex-1 flex items-center px-3 py-1">
                <input
                  type="text"
                  placeholder={
                    user
                      ? user.nickname || user.email
                      : isGuest
                      ? 'Guest Access Active'
                      : 'Enter engineer name or team...'
                  }
                  disabled={!!user || isGuest}
                  value={user ? user.nickname || user.email : isGuest ? 'Guest Access Active' : quickName}
                  onChange={(e) => setQuickName(e.target.value)}
                  className="w-full bg-transparent text-xs text-slate-900 dark:text-slate-100 placeholder-slate-400 dark:placeholder-slate-500 focus:outline-none disabled:opacity-75 font-sans"
                />
              </div>

              <button
                type="submit"
                className="flex items-center justify-center gap-2 bg-gradient-to-r from-brand-600 to-indigo-600 hover:from-brand-500 hover:to-indigo-500 text-white font-semibold px-5 py-2.5 rounded-xl text-xs shadow-md shadow-brand-500/25 transition active:scale-[0.98] min-h-[44px]"
              >
                <span>Launch Studio</span>
                <ArrowRight className="h-3.5 w-3.5" />
              </button>
            </form>

            {/* Instant Demo Benchmark Buttons */}
            <div className="flex flex-wrap items-center justify-center gap-2 mt-3 text-[11px] text-slate-500 dark:text-slate-400">
              <span className="text-slate-500">Quick benchmarks:</span>
              <button
                type="button"
                onClick={() => handleLaunchDemo('calculator')}
                className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg bg-white dark:bg-slate-900/80 hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-700 dark:text-slate-300 border border-slate-200 dark:border-slate-800 shadow-sm transition min-h-[32px]"
                title="Launch with Buggy Calculator demo project"
              >
                <Play className="h-2.5 w-2.5 text-brand-500 dark:text-brand-400" />
                <span>Buggy Calculator</span>
              </button>
              <button
                type="button"
                onClick={() => handleLaunchDemo('fastapi')}
                className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg bg-white dark:bg-slate-900/80 hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-700 dark:text-slate-300 border border-slate-200 dark:border-slate-800 shadow-sm transition min-h-[32px]"
                title="Launch with Async API demo project"
              >
                <Play className="h-2.5 w-2.5 text-emerald-500 dark:text-emerald-400" />
                <span>Async API</span>
              </button>
            </div>
          </div>
        </div>

        {/* =========================================================
            INTERACTIVE REPAIR SIMULATOR CARD (Bento Showcase)
           ========================================================= */}
        <div className="max-w-4xl mx-auto rounded-2xl border border-slate-200 dark:border-slate-800 bg-white/95 dark:bg-slate-900/70 shadow-xl dark:shadow-2xl backdrop-blur-md overflow-hidden mb-12">
          {/* Window Chrome Header */}
          <div className="flex flex-wrap items-center justify-between px-4 py-2.5 bg-slate-100/90 dark:bg-slate-950/80 border-b border-slate-200 dark:border-slate-800/80 gap-2">
            <div className="flex items-center gap-2">
              <span className="h-2.5 w-2.5 rounded-full bg-rose-500/80" />
              <span className="h-2.5 w-2.5 rounded-full bg-amber-500/80" />
              <span className="h-2.5 w-2.5 rounded-full bg-emerald-500/80" />
              <span className="ml-2 font-mono text-[11px] text-slate-500 dark:text-slate-400 flex items-center gap-1.5">
                <FileCode2 className="h-3 w-3 text-slate-400 dark:text-slate-500" />
                <span>demo_projects/calculator/src/math_ops.py</span>
              </span>
            </div>

            {/* Tab controls */}
            <div className="flex items-center gap-1">
              <button
                onClick={() => setActiveTab('diff')}
                className={`px-2.5 py-1 text-[11px] font-mono rounded-lg transition ${
                  activeTab === 'diff'
                    ? 'bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100 font-semibold shadow-sm'
                    : 'text-slate-500 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200'
                }`}
              >
                Unified Diff
              </button>
              <button
                onClick={() => setActiveTab('terminal')}
                className={`px-2.5 py-1 text-[11px] font-mono rounded-lg transition ${
                  activeTab === 'terminal'
                    ? 'bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100 font-semibold shadow-sm'
                    : 'text-slate-500 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200'
                }`}
              >
                Pytest Truth
              </button>
              <button
                onClick={() => setActiveTab('flow')}
                className={`px-2.5 py-1 text-[11px] font-mono rounded-lg transition ${
                  activeTab === 'flow'
                    ? 'bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100 font-semibold shadow-sm'
                    : 'text-slate-500 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200'
                }`}
              >
                Agent Stream
              </button>
            </div>
          </div>

          {/* Interactive Window Body */}
          <div className="p-4 font-mono text-xs overflow-x-auto min-h-[170px] bg-slate-50/70 dark:bg-slate-950/40">
            {activeTab === 'diff' && (
              <div className="space-y-1">
                <div className="text-slate-500">@@ -11,7 +11,7 @@ def calculate_discounted_total(price, quantity, discount):</div>
                <div className="text-slate-400">     subtotal = price * quantity</div>
                <div className="bg-rose-500/15 text-rose-700 dark:text-rose-300 px-2 py-0.5 rounded border border-rose-500/20 flex items-center gap-2">
                  <span className="select-none font-bold text-rose-500 dark:text-rose-400">-</span>
                  <span>    return subtotal - discount * 1.05  # Bug: incorrect tax operator precedence</span>
                </div>
                <div className="bg-emerald-500/15 text-emerald-700 dark:text-emerald-300 px-2 py-0.5 rounded border border-emerald-500/20 flex items-center gap-2">
                  <span className="select-none font-bold text-emerald-500 dark:text-emerald-400">+</span>
                  <span>    return (subtotal - discount) * 1.05  # Fix: strictly grouped operands</span>
                </div>
                <div className="text-slate-400">     # Preserved invariant: total cannot be negative</div>
              </div>
            )}

            {activeTab === 'terminal' && (
              <div className="space-y-1 text-slate-300">
                <div className="text-slate-500">$ pytest tests/ -v --tb=short</div>
                <div>collected 8 items</div>
                <div className="text-emerald-600 dark:text-emerald-400 flex items-center gap-2">
                  <Check className="h-3 w-3" /> tests/test_calculator.py::test_basic_addition PASSED
                </div>
                <div className="text-emerald-600 dark:text-emerald-400 flex items-center gap-2">
                  <Check className="h-3 w-3" /> tests/test_calculator.py::test_discount_precedence PASSED
                </div>
                <div className="text-emerald-600 dark:text-emerald-400 flex items-center gap-2">
                  <Check className="h-3 w-3" /> tests/test_calculator.py::test_edge_cases PASSED
                </div>
                <div className="pt-2 text-emerald-600 dark:text-emerald-300 font-bold border-t border-slate-800/80">
                  ================ 8 passed, 0 failed in 0.42s (Exit Code: 0) ================
                </div>
              </div>
            )}

            {activeTab === 'flow' && (
              <div className="space-y-2">
                <div className="flex items-center gap-2 text-blue-600 dark:text-blue-400">
                  <span className="px-1.5 py-0.5 rounded bg-blue-500/15 border border-blue-500/20 text-[10px]">
                    ARCHITECT
                  </span>
                  <span>Identified AssertionError in math_ops.py:14 (Operator grouping)</span>
                </div>
                <div className="flex items-center gap-2 text-indigo-600 dark:text-indigo-400">
                  <span className="px-1.5 py-0.5 rounded bg-indigo-500/15 border border-indigo-500/20 text-[10px]">
                    CODER
                  </span>
                  <span>Synthesized 1-line surgical patch; test suite strictly immutable</span>
                </div>
                <div className="flex items-center gap-2 text-emerald-600 dark:text-emerald-400">
                  <span className="px-1.5 py-0.5 rounded bg-emerald-500/15 border border-emerald-500/20 text-[10px]">
                    REVIEWER
                  </span>
                  <span>Pytest exit code: 0. Verified zero regressions. Approved.</span>
                </div>
              </div>
            )}
          </div>

          {/* Bottom Verification Banner */}
          <div className="px-4 py-2 bg-slate-100/90 dark:bg-slate-900 border-t border-slate-200 dark:border-slate-800 flex items-center justify-between text-[11px] text-slate-600 dark:text-slate-400">
            <span className="flex items-center gap-1.5">
              <ShieldCheck className="h-3.5 w-3.5 text-emerald-500 dark:text-emerald-400" />
              <span>Ground Truth: Pytest exit code 0 enforced by OS subprocess</span>
            </span>
            <span className="font-mono text-emerald-600 dark:text-emerald-400 font-semibold">100% PASS RATE</span>
          </div>
        </div>

        {/* =========================================================
            THE THREE AGENTS: Specialized Roles Bento Grid
           ========================================================= */}
        <div className="mb-14">
          <div className="text-center mb-8">
            <h2 className="text-2xl sm:text-3xl font-extrabold text-slate-900 dark:text-slate-100 tracking-tight mb-2">
              Three Specialized Agents. Single Ground Truth.
            </h2>
            <p className="text-xs sm:text-sm text-slate-600 dark:text-slate-400 max-w-xl mx-auto">
              Each agent has an isolated responsibility and strictly enforced security boundaries.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
            {/* Agent 1: Architect */}
            <div className="p-6 rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900/40 shadow-sm hover:shadow-md dark:shadow-none backdrop-blur-sm relative overflow-hidden group hover:border-blue-500/40 transition">
              <div className="h-10 w-10 rounded-xl bg-blue-500/10 border border-blue-500/20 text-blue-500 dark:text-blue-400 flex items-center justify-center mb-4">
                <Sparkles className="h-5 w-5" />
              </div>
              <h3 className="text-base font-bold text-slate-900 dark:text-slate-100 mb-1.5">Architect Agent</h3>
              <p className="text-xs text-slate-600 dark:text-slate-400 leading-relaxed mb-4">
                Inspects failing test diagnostics, error traces, and repository structure to formulate an exact, minimal repair plan.
              </p>
              <div className="space-y-1.5 pt-3 border-t border-slate-100 dark:border-slate-800/80 text-[11px] font-mono text-slate-700 dark:text-slate-300">
                <div className="flex items-center gap-1.5 text-blue-600 dark:text-blue-400">
                  <CheckCircle2 className="h-3.5 w-3.5" /> Root cause analysis
                </div>
                <div className="flex items-center gap-1.5 text-slate-500 dark:text-slate-400">
                  <CheckCircle2 className="h-3.5 w-3.5" /> Dependency call-graph mapping
                </div>
              </div>
            </div>

            {/* Agent 2: Coder */}
            <div className="p-6 rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900/40 shadow-sm hover:shadow-md dark:shadow-none backdrop-blur-sm relative overflow-hidden group hover:border-indigo-500/40 transition">
              <div className="h-10 w-10 rounded-xl bg-indigo-500/10 border border-indigo-500/20 text-indigo-500 dark:text-indigo-400 flex items-center justify-center mb-4">
                <Code2 className="h-5 w-5" />
              </div>
              <h3 className="text-base font-bold text-slate-900 dark:text-slate-100 mb-1.5">Coder Agent</h3>
              <p className="text-xs text-slate-600 dark:text-slate-400 leading-relaxed mb-4">
                Implements the surgical unified diff patch. Protected by security policies that prevent modifying test files.
              </p>
              <div className="space-y-1.5 pt-3 border-t border-slate-100 dark:border-slate-800/80 text-[11px] font-mono text-slate-700 dark:text-slate-300">
                <div className="flex items-center gap-1.5 text-indigo-600 dark:text-indigo-400">
                  <CheckCircle2 className="h-3.5 w-3.5" /> Unified diff synthesis
                </div>
                <div className="flex items-center gap-1.5 text-slate-500 dark:text-slate-400">
                  <CheckCircle2 className="h-3.5 w-3.5" /> Anti-tamper policy bounds
                </div>
              </div>
            </div>

            {/* Agent 3: Reviewer */}
            <div className="p-6 rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900/40 shadow-sm hover:shadow-md dark:shadow-none backdrop-blur-sm relative overflow-hidden group hover:border-emerald-500/40 transition">
              <div className="h-10 w-10 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-500 dark:text-emerald-400 flex items-center justify-center mb-4">
                <ShieldCheck className="h-5 w-5" />
              </div>
              <h3 className="text-base font-bold text-slate-900 dark:text-slate-100 mb-1.5">Reviewer Agent</h3>
              <p className="text-xs text-slate-600 dark:text-slate-400 leading-relaxed mb-4">
                Audits code changes against authoritative Pytest execution to eliminate regression risks and approve the fix.
              </p>
              <div className="space-y-1.5 pt-3 border-t border-slate-100 dark:border-slate-800/80 text-[11px] font-mono text-slate-700 dark:text-slate-300">
                <div className="flex items-center gap-1.5 text-emerald-600 dark:text-emerald-400">
                  <CheckCircle2 className="h-3.5 w-3.5" /> Subprocess Pytest gate
                </div>
                <div className="flex items-center gap-1.5 text-slate-500 dark:text-slate-400">
                  <CheckCircle2 className="h-3.5 w-3.5" /> Regression risk classification
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* =========================================================
            HOW IT WORKS: 4-Step Engineering Lifecycle
           ========================================================= */}
        <div className="mb-14 p-6 sm:p-8 rounded-3xl border border-slate-200 dark:border-slate-800/80 bg-slate-100/60 dark:bg-slate-900/30">
          <div className="text-center mb-8">
            <h2 className="text-xl sm:text-2xl font-bold text-slate-900 dark:text-slate-100 tracking-tight mb-2">
              Autonomous Repair Lifecycle
            </h2>
            <p className="text-xs text-slate-600 dark:text-slate-400">
              From failing repository upload to downloadable verified archive.
            </p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 text-xs">
            <div className="p-4 rounded-xl bg-white dark:bg-slate-950/60 border border-slate-200 dark:border-slate-800/60 shadow-sm dark:shadow-none">
              <div className="text-brand-600 dark:text-brand-400 font-mono font-bold text-sm mb-1.5">01. INGEST</div>
              <h4 className="font-semibold text-slate-900 dark:text-slate-200 mb-1">Upload Project</h4>
              <p className="text-slate-600 dark:text-slate-400 leading-relaxed">
                Upload your failing Python repo ZIP. Fixsembly creates an isolated disk workspace.
              </p>
            </div>

            <div className="p-4 rounded-xl bg-white dark:bg-slate-950/60 border border-slate-200 dark:border-slate-800/60 shadow-sm dark:shadow-none">
              <div className="text-blue-600 dark:text-blue-400 font-mono font-bold text-sm mb-1.5">02. DIAGNOSE</div>
              <h4 className="font-semibold text-slate-900 dark:text-slate-200 mb-1">Architect Analysis</h4>
              <p className="text-slate-600 dark:text-slate-400 leading-relaxed">
                Pytest baseline executes. Architect agent maps root causes without modifying files.
              </p>
            </div>

            <div className="p-4 rounded-xl bg-white dark:bg-slate-950/60 border border-slate-200 dark:border-slate-800/60 shadow-sm dark:shadow-none">
              <div className="text-indigo-600 dark:text-indigo-400 font-mono font-bold text-sm mb-1.5">03. SYNTHESIZE</div>
              <h4 className="font-semibold text-slate-900 dark:text-slate-200 mb-1">Coder Patching</h4>
              <p className="text-slate-600 dark:text-slate-400 leading-relaxed">
                Coder writes minimal patches bounded strictly by test file immutability rules.
              </p>
            </div>

            <div className="p-4 rounded-xl bg-white dark:bg-slate-950/60 border border-slate-200 dark:border-slate-800/60 shadow-sm dark:shadow-none">
              <div className="text-emerald-600 dark:text-emerald-400 font-mono font-bold text-sm mb-1.5">04. VERIFY</div>
              <h4 className="font-semibold text-slate-900 dark:text-slate-200 mb-1">Reviewer Gate</h4>
              <p className="text-slate-600 dark:text-slate-400 leading-relaxed">
                Subprocess Pytest validates exit code 0. Reviewer audits regression risk before download.
              </p>
            </div>
          </div>
        </div>

        {/* =========================================================
            BOTTOM CONVERSION CTA BANNER
           ========================================================= */}
        <div className="rounded-3xl border border-brand-500/25 dark:border-brand-500/30 bg-gradient-to-b from-brand-50/80 via-white to-slate-50 dark:from-brand-500/10 dark:via-slate-900/60 dark:to-slate-950 p-8 sm:p-10 text-center relative overflow-hidden shadow-xl dark:shadow-2xl mb-8">
          <div className="max-w-xl mx-auto space-y-4">
            <h3 className="text-2xl sm:text-3xl font-black text-slate-900 dark:text-slate-100 tracking-tight">
              Ready to Turn Red Tests Green?
            </h3>
            <p className="text-xs sm:text-sm text-slate-600 dark:text-slate-300 leading-relaxed">
              Launch Fixsembly Studio instantly in guest mode or explore interactive documentation.
            </p>

            <div className="flex flex-wrap items-center justify-center gap-3 pt-2">
              <button
                onClick={handleQuickStart}
                className="flex items-center gap-2 bg-gradient-to-r from-brand-600 to-indigo-600 hover:from-brand-500 hover:to-indigo-500 text-white font-semibold px-6 py-3 rounded-xl text-xs shadow-lg shadow-brand-500/25 transition active:scale-[0.98] min-h-[44px]"
              >
                <span>Launch Repair Studio</span>
                <ArrowRight className="h-4 w-4" />
              </button>

              <Link
                to="/docs"
                className="flex items-center gap-2 bg-white dark:bg-slate-900 hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-700 dark:text-slate-300 border border-slate-300 dark:border-slate-700 font-medium px-5 py-3 rounded-xl text-xs transition shadow-sm min-h-[44px]"
              >
                <BookOpen className="h-4 w-4 text-slate-500 dark:text-slate-400" />
                <span>Documentation</span>
              </Link>
            </div>
          </div>
        </div>

        {/* =========================================================
            CLEAN DEVELOPER FOOTER
           ========================================================= */}
        <div className="border-t border-slate-200 dark:border-slate-800/80 pt-6 pb-2 flex flex-col sm:flex-row items-center justify-between gap-3 text-xs text-slate-600 dark:text-slate-400 font-mono">
          <div className="flex items-center gap-2">
            <FixsemblyIcon size={18} />
            <span className="text-slate-900 dark:text-slate-300 font-medium font-sans">Fixsembly</span>
            <span>• Three Agents. One Verified Fix.</span>
          </div>

          <div className="flex items-center gap-4">
            <Link to="/docs" className="hover:text-slate-900 dark:hover:text-slate-200 transition">
              Docs
            </Link>
            <Link to="/history" className="hover:text-slate-900 dark:hover:text-slate-200 transition">
              History
            </Link>
            <Link to="/health" className="hover:text-slate-900 dark:hover:text-slate-200 transition">
              Health
            </Link>
            <a
              href="https://github.com/Ravikiran9988/AegisCode"
              target="_blank"
              rel="noreferrer"
              className="hover:text-slate-900 dark:hover:text-slate-200 transition flex items-center gap-1"
            >
              <span>GitHub</span>
              <ExternalLink className="h-3 w-3" />
            </a>
          </div>
        </div>
      </div>
    </div>
  );
}

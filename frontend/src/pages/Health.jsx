import { useState, useEffect } from 'react';
import { HeartPulse, CheckCircle2, XCircle, Database, Cpu, Clock, RefreshCw, Zap } from 'lucide-react';
import { getSystemHealth } from '../api/auth';

export default function Health() {
  const [health, setHealth] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');

  const checkHealth = async () => {
    setIsLoading(true);
    setError('');
    try {
      const data = await getSystemHealth();
      setHealth(data);
    } catch (err) {
      setError(err.message || 'Failed to connect to backend engine.');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    checkHealth();
  }, []);

  const isHealthy = health?.status === 'ok';

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between pb-4 border-b border-slate-800">
        <div>
          <h2 className="text-xl font-bold tracking-tight text-white flex items-center gap-2">
            <HeartPulse className="h-5 w-5 text-brand-400" />
            <span>System Health & Telemetry</span>
          </h2>
          <p className="text-xs text-slate-400 mt-1">
            Status of backend FastAPI services, SQLAlchemy database, and LLM providers.
          </p>
        </div>

        <button
          onClick={checkHealth}
          disabled={isLoading}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl border border-slate-800 bg-slate-900 hover:bg-slate-800 text-xs font-mono text-slate-300 transition"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${isLoading ? 'animate-spin' : ''}`} />
          <span>Ping Engine</span>
        </button>
      </div>

      {error && (
        <div className="p-4 rounded-2xl bg-rose-500/10 border border-rose-500/20 text-rose-300 text-xs flex items-center gap-3">
          <XCircle className="h-5 w-5 text-rose-400 flex-shrink-0" />
          <div>
            <p className="font-semibold">Backend Unreachable</p>
            <p className="text-rose-400/80 mt-0.5">{error}</p>
          </div>
        </div>
      )}

      {/* Main Status Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {/* Overall Status */}
        <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-5 backdrop-blur-sm">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <Zap className="h-4 w-4 text-brand-400" />
              <span className="text-xs font-semibold uppercase tracking-wider text-slate-300 font-mono">
                Engine Status
              </span>
            </div>
            <span
              className={`h-2.5 w-2.5 rounded-full ${isHealthy ? 'bg-emerald-400 shadow-lg shadow-emerald-500/50' : 'bg-rose-500'}`}
            ></span>
          </div>
          <div className="text-2xl font-bold text-white capitalize mb-1">
            {health?.status || 'Offline'}
          </div>
          <p className="text-xs text-slate-400 font-mono">
            {health?.app_name || 'Fixsembly'} v{health?.version || '2.0.0'}
          </p>
        </div>

        {/* Database Status */}
        <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-5 backdrop-blur-sm">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <Database className="h-4 w-4 text-blue-400" />
              <span className="text-xs font-semibold uppercase tracking-wider text-slate-300 font-mono">
                Database
              </span>
            </div>
            <span
              className={`h-2.5 w-2.5 rounded-full ${
                health?.database === 'connected' ? 'bg-emerald-400' : 'bg-rose-500'
              }`}
            ></span>
          </div>
          <div className="text-2xl font-bold text-white capitalize mb-1">
            {health?.database || 'Disconnected'}
          </div>
          <p className="text-xs text-slate-400 font-mono">
            SQLAlchemy ORM + SQLite / PostgreSQL
          </p>
        </div>
      </div>

      {/* Telemetry Breakdown */}
      <div className="rounded-2xl border border-slate-800 bg-slate-900/40 p-5 space-y-4">
        <h3 className="text-xs font-semibold uppercase tracking-wider font-mono text-slate-300">
          Subsystem Diagnostics
        </h3>

        <div className="divide-y divide-slate-800/60 text-xs">
          <div className="py-2.5 flex items-center justify-between font-mono">
            <span className="text-slate-400">LLM Provider Mode</span>
            <span className="text-brand-300 font-semibold">{health?.llm_provider || 'openai_compatible (Groq)'}</span>
          </div>

          <div className="py-2.5 flex items-center justify-between font-mono">
            <span className="text-slate-400">Execution Backend</span>
            <span className="text-slate-200">Local Subprocess (Sandboxed)</span>
          </div>

          <div className="py-2.5 flex items-center justify-between font-mono">
            <span className="text-slate-400">Multi-Agent Engine</span>
            <span className="text-emerald-400">LangGraph v1.2 StateGraph</span>
          </div>

          <div className="py-2.5 flex items-center justify-between font-mono">
            <span className="text-slate-400">Last Telemetry Check</span>
            <span className="text-slate-400">
              {health?.timestamp ? new Date(health.timestamp).toLocaleTimeString() : 'Never'}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}

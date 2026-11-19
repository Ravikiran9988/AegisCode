import { useState, useRef, useEffect } from 'react';
import { Terminal as TerminalIcon, Copy, Check, Search, ArrowDown } from 'lucide-react';

export default function Terminal({ output = '', title = 'Pytest Execution Output', isRunning = false }) {
  const [copied, setCopied] = useState(false);
  const [filter, setFilter] = useState('');
  const [autoScroll, setAutoScroll] = useState(true);
  const terminalRef = useRef(null);

  useEffect(() => {
    if (autoScroll && terminalRef.current) {
      terminalRef.current.scrollTop = terminalRef.current.scrollHeight;
    }
  }, [output, autoScroll]);

  const handleCopy = () => {
    navigator.clipboard.writeText(output);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const lines = (output || 'No output recorded yet.').split('\n');
  const filteredLines = filter
    ? lines.filter((l) => l.toLowerCase().includes(filter.toLowerCase()))
    : lines;

  function formatLine(line) {
    if (line.includes('PASSED') || line.includes('=== 1 passed') || line.includes('all tests pass')) {
      return 'text-emerald-400 font-semibold';
    }
    if (line.includes('FAILED') || line.includes('ERRORS') || line.includes('AssertionError') || line.startsWith('E   ')) {
      return 'text-rose-400 font-medium';
    }
    if (line.startsWith('rootdir:') || line.includes('test session starts')) {
      return 'text-cyan-400';
    }
    if (line.includes('warning') || line.includes('Warning:')) {
      return 'text-amber-400';
    }
    return 'text-slate-300';
  }

  return (
    <div className="rounded-2xl border border-slate-800/80 bg-slate-950 overflow-hidden shadow-2xl flex flex-col h-[420px]">
      {/* Terminal Title Bar */}
      <div className="flex items-center justify-between px-4 py-2.5 bg-slate-900 border-b border-slate-800 text-xs">
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1.5 mr-2">
            <span className="h-3 w-3 rounded-full bg-rose-500/80 inline-block"></span>
            <span className="h-3 w-3 rounded-full bg-amber-500/80 inline-block"></span>
            <span className="h-3 w-3 rounded-full bg-emerald-500/80 inline-block"></span>
          </div>
          <TerminalIcon className="h-4 w-4 text-slate-400" />
          <span className="font-mono text-slate-300 font-medium">{title}</span>
          {isRunning && (
            <span className="flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-mono bg-brand-500/20 text-brand-300 border border-brand-500/30 animate-pulse">
              Running
            </span>
          )}
        </div>

        {/* Toolbar */}
        <div className="flex items-center gap-2">
          {/* Search */}
          <div className="relative">
            <Search className="h-3.5 w-3.5 text-slate-500 absolute left-2 top-2" />
            <input
              type="text"
              placeholder="Filter log..."
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
              className="bg-slate-950 border border-slate-800 rounded-lg pl-7 pr-2 py-1 text-[11px] font-mono text-slate-200 placeholder-slate-600 focus:outline-none focus:border-brand-500 w-28 sm:w-36 transition"
            />
          </div>

          {/* Auto-scroll toggle */}
          <button
            onClick={() => setAutoScroll(!autoScroll)}
            className={`p-1.5 rounded-lg border text-xs transition ${
              autoScroll
                ? 'bg-brand-500/20 border-brand-500/30 text-brand-300'
                : 'bg-slate-950 border-slate-800 text-slate-500 hover:text-slate-300'
            }`}
            title="Auto-scroll to bottom"
          >
            <ArrowDown className="h-3.5 w-3.5" />
          </button>

          {/* Copy */}
          <button
            onClick={handleCopy}
            className="flex items-center gap-1 px-2 py-1 bg-slate-950 hover:bg-slate-800 border border-slate-800 rounded-lg text-[11px] font-mono text-slate-300 transition"
            title="Copy output"
          >
            {copied ? <Check className="h-3 w-3 text-emerald-400" /> : <Copy className="h-3 w-3" />}
            <span className="hidden sm:inline">{copied ? 'Copied' : 'Copy'}</span>
          </button>
        </div>
      </div>

      {/* Terminal Content */}
      <div
        ref={terminalRef}
        className="flex-1 p-4 font-mono text-[11.5px] leading-relaxed overflow-y-auto terminal-scroll bg-[#090d16] text-slate-300 selection:bg-brand-500/40"
      >
        {filteredLines.map((line, idx) => (
          <div key={idx} className="flex hover:bg-slate-800/40 px-1 rounded transition-colors">
            <span className="text-slate-500 select-none w-10 flex-shrink-0 text-right pr-3 font-mono text-[10px]">
              {idx + 1}
            </span>
            <span className={`whitespace-pre-wrap break-all ${formatLine(line)}`}>
              {line || ' '}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

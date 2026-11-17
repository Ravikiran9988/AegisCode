import { useState } from 'react';
import { DiffEditor } from '@monaco-editor/react';
import { Columns, AlignJustify, FileCode, Plus, Minus, Check } from 'lucide-react';
import { useTheme } from '../context/ThemeContext';

export default function MonacoDiff({ diffData, codeChange }) {
  const { isDark } = useTheme();
  const [sideBySide, setSideBySide] = useState(true);

  if (!diffData && !codeChange) {
    return (
      <div className="rounded-2xl border border-slate-800/80 bg-slate-900/40 p-8 text-center text-slate-500">
        <FileCode className="h-8 w-8 mx-auto mb-2 text-slate-600" />
        <p className="text-sm font-medium">No code modifications synthesized yet</p>
        <p className="text-xs text-slate-500 mt-1">
          When the Coder Agent applies a targeted repair, the syntax-highlighted diff will appear here.
        </p>
      </div>
    );
  }

  const rawDiff = diffData?.diff || '';
  const changedFiles = diffData?.changed_files || (codeChange?.file_path ? [codeChange.file_path] : []);
  const additions = diffData?.additions || 0;
  const deletions = diffData?.deletions || 0;

  // Derive original and modified contents or display the patch
  // If we have a unified diff, we parse it into left/right or show full patch
  let originalContent = '';
  let modifiedContent = '';

  if (rawDiff) {
    // Basic reconstruction for Monaco diff view
    const origLines = [];
    const modLines = [];
    const diffLines = rawDiff.split('\n');

    for (const line of diffLines) {
      if (line.startsWith('---') || line.startsWith('+++') || line.startsWith('@@')) {
        continue;
      }
      if (line.startsWith('-')) {
        origLines.push(line.slice(1));
      } else if (line.startsWith('+')) {
        modLines.push(line.slice(1));
      } else if (line.startsWith(' ')) {
        origLines.push(line.slice(1));
        modLines.push(line.slice(1));
      } else {
        origLines.push(line);
        modLines.push(line);
      }
    }
    originalContent = origLines.join('\n');
    modifiedContent = modLines.join('\n');
  } else if (codeChange?.patch) {
    originalContent = '# Original file contents before repair';
    modifiedContent = codeChange.patch;
  }

  return (
    <div className="rounded-2xl border border-slate-800/80 bg-slate-950 overflow-hidden shadow-2xl flex flex-col h-[460px]">
      {/* Diff Toolbar */}
      <div className="flex items-center justify-between px-4 py-2.5 bg-slate-900 border-b border-slate-800 text-xs">
        {/* Changed file tabs */}
        <div className="flex items-center gap-2 overflow-x-auto">
          <FileCode className="h-4 w-4 text-brand-400 flex-shrink-0" />
          {changedFiles.map((f, i) => (
            <span
              key={i}
              className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-slate-800/90 border border-slate-700/80 text-slate-200 font-mono text-[11px]"
            >
              <span>{f}</span>
            </span>
          ))}

          {/* Additions / Deletions count */}
          {(additions > 0 || deletions > 0) && (
            <div className="flex items-center gap-1 font-mono text-[11px] ml-2">
              <span className="text-emerald-400 flex items-center">
                <Plus className="h-3 w-3" />
                {additions}
              </span>
              <span className="text-rose-400 flex items-center">
                <Minus className="h-3 w-3" />
                {deletions}
              </span>
            </div>
          )}
        </div>

        {/* View Mode Toggle */}
        <div className="flex items-center gap-1 bg-slate-950 p-0.5 rounded-lg border border-slate-800">
          <button
            onClick={() => setSideBySide(true)}
            className={`flex items-center gap-1 px-2 py-1 rounded text-[11px] font-mono transition ${
              sideBySide
                ? 'bg-brand-500/20 text-brand-300 border border-brand-500/30'
                : 'text-slate-400 hover:text-slate-200'
            }`}
            title="Side by side diff"
          >
            <Columns className="h-3 w-3" />
            <span className="hidden sm:inline">Split</span>
          </button>
          <button
            onClick={() => setSideBySide(false)}
            className={`flex items-center gap-1 px-2 py-1 rounded text-[11px] font-mono transition ${
              !sideBySide
                ? 'bg-brand-500/20 text-brand-300 border border-brand-500/30'
                : 'text-slate-400 hover:text-slate-200'
            }`}
            title="Inline diff"
          >
            <AlignJustify className="h-3 w-3" />
            <span className="hidden sm:inline">Inline</span>
          </button>
        </div>
      </div>

      {/* Monaco Editor Diff Container */}
      <div className="flex-1 relative">
        <DiffEditor
          height="100%"
          language="python"
          original={originalContent}
          modified={modifiedContent}
          theme={isDark ? 'vs-dark' : 'light'}
          options={{
            renderSideBySide: sideBySide,
            readOnly: true,
            minimap: { enabled: false },
            fontSize: 12,
            lineNumbers: 'on',
            scrollBeyondLastLine: false,
            automaticLayout: true,
            fontFamily: 'JetBrains Mono, monospace',
            wordWrap: 'on',
          }}
        />
      </div>
    </div>
  );
}

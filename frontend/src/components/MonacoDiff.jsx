import { Editor } from '@monaco-editor/react';
import { FileCode, Plus, Minus } from 'lucide-react';
import { useTheme } from '../context/ThemeContext';

export default function MonacoDiff({ diffData, codeChange }) {
  const { isDark } = useTheme();

  if (!diffData && !codeChange) {
    return (
      <div className="rounded-2xl border border-slate-800/80 bg-slate-900/40 p-8 text-center text-slate-500">
        <FileCode className="h-8 w-8 mx-auto mb-2 text-slate-600" />
        <p className="text-sm font-medium">No code modifications synthesized yet</p>
        <p className="text-xs text-slate-500 mt-1">
          The actual unified patch will appear here after the Coder Agent changes a file.
        </p>
      </div>
    );
  }

  // Render the authoritative patch verbatim. Reconstructing file contents from
  // unified-diff fragments loses unchanged regions and corrupts multi-hunk diffs.
  const patch = diffData?.diff || codeChange?.patch || '';
  const changedFiles = diffData?.changed_files ||
    (codeChange?.file_path ? [codeChange.file_path] : []);
  const additions = diffData?.additions ?? null;
  const deletions = diffData?.deletions ?? null;
  const language = diffData?.diff ? 'diff' : (
    codeChange?.file_path?.endsWith('.py') ? 'python' : 'plaintext'
  );

  return (
    <div className="rounded-2xl border border-slate-800/80 bg-slate-950 overflow-hidden shadow-2xl flex flex-col h-[460px]">
      <div className="flex items-center justify-between gap-3 px-4 py-2.5 bg-slate-900 border-b border-slate-800 text-xs">
        <div className="flex items-center gap-2 overflow-x-auto min-w-0">
          <FileCode className="h-4 w-4 text-brand-400 flex-shrink-0" />
          {changedFiles.length ? changedFiles.map((file, index) => (
            <span
              key={`${file}-${index}`}
              className="px-2.5 py-1 rounded-lg bg-slate-800/90 border border-slate-700/80 text-slate-200 font-mono text-[11px] whitespace-nowrap"
            >
              {file}
            </span>
          )) : (
            <span className="text-slate-400 font-mono">Patch preview</span>
          )}
        </div>

        {(additions !== null || deletions !== null) && (
          <div className="flex items-center gap-2 font-mono text-[11px] flex-shrink-0">
            {additions !== null && (
              <span className="text-emerald-400 inline-flex items-center">
                <Plus className="h-3 w-3" />{additions}
              </span>
            )}
            {deletions !== null && (
              <span className="text-rose-400 inline-flex items-center">
                <Minus className="h-3 w-3" />{deletions}
              </span>
            )}
          </div>
        )}
      </div>

      <div className="flex-1 relative">
        <Editor
          height="100%"
          language={language}
          value={patch}
          theme={isDark ? 'vs-dark' : 'light'}
          options={{
            readOnly: true,
            minimap: { enabled: false },
            fontSize: 12,
            lineNumbers: 'on',
            scrollBeyondLastLine: false,
            automaticLayout: true,
            fontFamily: 'JetBrains Mono, monospace',
            wordWrap: 'on',
            renderWhitespace: 'selection',
            folding: true,
          }}
        />
      </div>
    </div>
  );
}

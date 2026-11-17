import { useState, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  UploadCloud,
  FileArchive,
  PlayCircle,
  Sliders,
  AlertCircle,
  CheckCircle2,
  Loader2,
  Sparkles,
  Info,
} from 'lucide-react';
import { uploadProject } from '../api/projects';
import { createRun, startRepair } from '../api/runs';

export default function NewRepair() {
  const navigate = useNavigate();
  const fileInputRef = useRef(null);

  const [file, setFile] = useState(null);
  const [maxIterations, setMaxIterations] = useState(5);
  const [isUploading, setIsUploading] = useState(false);
  const [stepState, setStepState] = useState(''); // 'uploading', 'baseline', 'launching'
  const [error, setError] = useState('');
  const [isDragging, setIsDragging] = useState(false);

  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragging(false);
    const dropped = e.dataTransfer.files[0];
    if (dropped && dropped.name.endsWith('.zip')) {
      setFile(dropped);
      setError('');
    } else {
      setError('Please upload a valid .zip archive of a Python project.');
    }
  };

  const handleFileChange = (e) => {
    const selected = e.target.files[0];
    if (selected && selected.name.endsWith('.zip')) {
      setFile(selected);
      setError('');
    } else if (selected) {
      setError('Only .zip archives are supported.');
    }
  };

  const handleLaunchDemo = async () => {
    // Generate a demo zip in memory or fetch demo project
    setIsUploading(true);
    setStepState('Preparing demo project...');
    setError('');

    try {
      // Create a minimal synthetic demo zip in browser if needed, or prompt user
      const response = await fetch('/api/health');
      if (!response.ok) throw new Error('Backend is currently unreachable');

      // We can upload a demo calculator archive
      // Let's create a JS Zip or trigger demo upload
      setStepState('Uploading Buggy Calculator benchmark...');
      // Using an actual sample zip:
      const dummyContent = 'dummy'; // We can trigger sample via standard file or alert
    } catch (err) {
      setError(err.message || 'Failed to initialize demo');
      setIsUploading(false);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!file) {
      setError('Please select a project .zip archive.');
      return;
    }

    setIsUploading(true);
    setError('');

    try {
      // Step 1: Upload project archive
      setStepState('1/3 Extracting & validating project archive...');
      const uploadRes = await uploadProject(file);
      const projectId = uploadRes.project_id;

      // Step 2: Create run & execute baseline pytest
      setStepState('2/3 Executing baseline Pytest assessment...');
      const runRes = await createRun(projectId, maxIterations);
      const runId = runRes.run_id;

      // If project tests already pass 100%, we don't need a repair loop
      if (runRes.status === 'passed') {
        navigate(`/repair/${runId}`);
        return;
      }

      // Step 3: Trigger background multi-agent repair loop
      setStepState('3/3 Deploying Architect, Coder & Reviewer agents...');
      await startRepair(runId);

      // Navigate to live studio
      navigate(`/repair/${runId}`);
    } catch (err) {
      setError(err.message || 'Failed to start repair run.');
      setIsUploading(false);
    }
  };

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      {/* Header */}
      <div className="pb-4 border-b border-slate-800">
        <h2 className="text-xl font-bold tracking-tight text-white flex items-center gap-2">
          <PlayCircle className="h-5 w-5 text-brand-400" />
          <span>Launch Autonomous Repair</span>
        </h2>
        <p className="text-xs text-slate-400 mt-1">
          Upload any failing Python project with Pytest tests. Fixsembly will execute baseline diagnostics, formulate a repair plan, and synthesize verified patches.
        </p>
      </div>

      {error && (
        <div className="p-4 rounded-2xl bg-rose-500/10 border border-rose-500/20 text-rose-300 text-xs flex items-center gap-2.5">
          <AlertCircle className="h-4 w-4 text-rose-400 flex-shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Main Upload Card */}
      <form onSubmit={handleSubmit} className="space-y-6">
        <div
          onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
          onDragLeave={() => setIsDragging(false)}
          onDrop={handleDrop}
          onClick={() => fileInputRef.current?.click()}
          className={`cursor-pointer rounded-3xl border-2 border-dashed p-10 text-center transition-all duration-200 ${
            isDragging
              ? 'border-brand-500 bg-brand-500/10'
              : file
              ? 'border-emerald-500/50 bg-emerald-500/5'
              : 'border-slate-800 bg-slate-900/40 hover:border-slate-700 hover:bg-slate-900/60'
          }`}
        >
          <input
            type="file"
            ref={fileInputRef}
            onChange={handleFileChange}
            accept=".zip"
            className="hidden"
          />

          {file ? (
            <div className="space-y-3">
              <div className="h-12 w-12 rounded-2xl bg-emerald-500/15 border border-emerald-500/30 text-emerald-400 flex items-center justify-center mx-auto">
                <FileArchive className="h-6 w-6" />
              </div>
              <div>
                <p className="text-sm font-semibold text-slate-100">{file.name}</p>
                <p className="text-xs font-mono text-slate-400 mt-0.5">
                  {(file.size / 1024 / 1024).toFixed(2)} MB • Ready for Pytest analysis
                </p>
              </div>
              <span className="inline-block text-[11px] text-brand-400 hover:underline">
                Click or drop another file to replace
              </span>
            </div>
          ) : (
            <div className="space-y-3">
              <div className="h-12 w-12 rounded-2xl bg-brand-500/10 border border-brand-500/20 text-brand-400 flex items-center justify-center mx-auto">
                <UploadCloud className="h-6 w-6" />
              </div>
              <div>
                <p className="text-sm font-semibold text-slate-200">
                  Drop your Python project archive (.zip) here
                </p>
                <p className="text-xs text-slate-500 mt-1">
                  or click to browse from your computer (up to 50MB)
                </p>
              </div>
              <div className="flex items-center justify-center gap-2 text-[11px] font-mono text-slate-400">
                <span className="flex items-center gap-1">
                  <CheckCircle2 className="h-3 w-3 text-emerald-400" /> Auto-extract
                </span>
                <span>•</span>
                <span className="flex items-center gap-1">
                  <CheckCircle2 className="h-3 w-3 text-emerald-400" /> Ephemeral Git repo
                </span>
                <span>•</span>
                <span className="flex items-center gap-1">
                  <CheckCircle2 className="h-3 w-3 text-emerald-400" /> Pytest runner
                </span>
              </div>
            </div>
          )}
        </div>

        {/* Configuration Box */}
        <div className="rounded-2xl border border-slate-800 bg-slate-900/40 p-5 space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Sliders className="h-4 w-4 text-brand-400" />
              <label className="text-xs font-semibold text-slate-200">
                Maximum Repair Iterations
              </label>
            </div>
            <span className="text-xs font-mono font-bold text-brand-400 bg-brand-500/10 border border-brand-500/20 px-2.5 py-0.5 rounded-lg">
              {maxIterations} Iteration{maxIterations > 1 ? 's' : ''}
            </span>
          </div>

          <input
            type="range"
            min="1"
            max="10"
            value={maxIterations}
            onChange={(e) => setMaxIterations(parseInt(e.target.value, 10))}
            className="w-full accent-brand-500 cursor-pointer h-1.5 bg-slate-800 rounded-lg"
          />

          <div className="flex items-center justify-between text-[11px] text-slate-500 font-mono">
            <span>Fast fix (1-2)</span>
            <span>Recommended (5)</span>
            <span>Deep search (10)</span>
          </div>

          <div className="flex items-start gap-2 p-3 rounded-xl bg-slate-950/70 border border-slate-800/80 text-[11px] text-slate-400">
            <Info className="h-4 w-4 text-brand-400 flex-shrink-0 mt-0.5" />
            <span>
              If a repair stalls with repeated failures, Fixsembly’s loop detector halts execution early to prevent unnecessary LLM token consumption.
            </span>
          </div>
        </div>

        {/* Action Button */}
        <button
          type="submit"
          disabled={!file || isUploading}
          className="w-full py-3.5 rounded-2xl bg-gradient-to-r from-brand-600 via-indigo-600 to-emerald-600 hover:from-brand-500 hover:to-emerald-500 text-white font-semibold text-sm shadow-xl shadow-brand-500/20 flex items-center justify-center gap-2 transition disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {isUploading ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              <span>{stepState}</span>
            </>
          ) : (
            <>
              <Sparkles className="h-4 w-4" />
              <span>Launch Autonomous Fixsembly Pipeline</span>
            </>
          )}
        </button>
      </form>
    </div>
  );
}

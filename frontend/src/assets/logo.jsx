import React from 'react';

/**
 * Fixsembly Brand Identity Assets
 * Concept: Tripartite Engineering Convergence: Three specialized agent nodes
 * (Architect, Coder, Reviewer) interlocking into a single verified assembly core.
 */

export function FixsemblyIcon({ className = "h-8 w-8", size = 32 }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 48 48"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      aria-label="Fixsembly Icon"
    >
      <defs>
        {/* Architect Node Gradient */}
        <linearGradient id="fx-arch-grad" x1="24" y1="4" x2="10" y2="28" gradientUnits="userSpaceOnUse">
          <stop stopColor="#38bdf8" />
          <stop offset="1" stopColor="#0284c7" />
        </linearGradient>

        {/* Coder Node Gradient */}
        <linearGradient id="fx-coder-grad" x1="10" y1="28" x2="38" y2="28" gradientUnits="userSpaceOnUse">
          <stop stopColor="#818cf8" />
          <stop offset="1" stopColor="#4f46e5" />
        </linearGradient>

        {/* Reviewer Node Gradient */}
        <linearGradient id="fx-rev-grad" x1="38" y1="28" x2="24" y2="4" gradientUnits="userSpaceOnUse">
          <stop stopColor="#34d399" />
          <stop offset="1" stopColor="#059669" />
        </linearGradient>

        {/* Central Core Glow */}
        <radialGradient id="fx-core-glow" cx="24" cy="24" r="10" gradientUnits="userSpaceOnUse">
          <stop stopColor="#ffffff" stopOpacity="0.9" />
          <stop offset="0.6" stopColor="#6366f1" stopOpacity="0.4" />
          <stop offset="1" stopColor="#0f172a" stopOpacity="0" />
        </radialGradient>
      </defs>

      {/* Hexagonal Outer Track */}
      <path
        d="M24 4L41.32 14V34L24 44L6.68 34V14L24 4Z"
        stroke="currentColor"
        className="text-slate-400 dark:text-slate-600"
        strokeWidth="1.5"
        strokeLinejoin="round"
        strokeDasharray="2 3"
        opacity="0.6"
      />

      {/* Node 1: Architect (Top apex segment) */}
      <path
        d="M24 6L38 14.5L30 20L24 16L18 20L10 14.5L24 6Z"
        fill="url(#fx-arch-grad)"
        fillOpacity="0.85"
      />

      {/* Node 2: Coder (Bottom-left segment) */}
      <path
        d="M9 16.5L16.5 21L16.5 29L10 33L4 23.5L9 16.5Z"
        fill="url(#fx-coder-grad)"
        fillOpacity="0.85"
      />

      {/* Node 3: Reviewer (Bottom-right segment) */}
      <path
        d="M39 16.5L44 23.5L38 33L31.5 29L31.5 21L39 16.5Z"
        fill="url(#fx-rev-grad)"
        fillOpacity="0.85"
      />

      {/* Interlocking Convergence Bridge Base */}
      <path
        d="M16.5 30.5L24 35L31.5 30.5L31.5 38.5L24 43L16.5 38.5V30.5Z"
        className="fill-slate-300 dark:fill-slate-800 stroke-slate-400 dark:stroke-slate-600"
        strokeWidth="1.5"
      />

      {/* Central Verified Core Node */}
      <circle cx="24" cy="24" r="5" className="fill-slate-100 dark:fill-slate-900" stroke="#6366f1" strokeWidth="2" />
      <circle cx="24" cy="24" r="2.5" fill="#34d399" />
      <circle cx="24" cy="24" r="7" fill="url(#fx-core-glow)" pointerEvents="none" />
    </svg>
  );
}

export function FixsemblyWordmark({ className = "h-7", showTagline = false }) {
  return (
    <div className={`flex items-center gap-2.5 ${className}`}>
      <FixsemblyIcon size={30} className="flex-shrink-0" />
      <div className="flex flex-col">
        <div className="flex items-center gap-2">
          <span className="font-extrabold text-lg tracking-tight text-slate-900 dark:bg-gradient-to-r dark:from-white dark:via-slate-100 dark:to-slate-300 dark:bg-clip-text dark:text-transparent font-sans">
            Fixsembly
          </span>
        </div>
        {showTagline && (
          <span className="hidden sm:inline text-[10px] text-slate-500 dark:text-slate-400 tracking-tight font-medium font-sans -mt-0.5">
            Three Agents. One Verified Fix.
          </span>
        )}
      </div>
    </div>
  );
}

export function FixsemblyLoader({ size = "md", text = "Agents Coordinated..." }) {
  const iconSize = size === "lg" ? 48 : size === "sm" ? 24 : 36;
  return (
    <div className="flex flex-col items-center justify-center p-8 space-y-4 text-center">
      <div className="relative">
        <div className="animate-spin duration-3000">
          <FixsemblyIcon size={iconSize} />
        </div>
        <div className="absolute inset-0 rounded-full bg-brand-500/20 blur-xl animate-pulse" />
      </div>
      {text && (
        <div className="space-y-1">
          <p className="text-xs font-mono font-medium text-slate-200 tracking-wide uppercase">
            {text}
          </p>
          <p className="text-[11px] text-slate-500 font-sans">
            Red to green, automatically
          </p>
        </div>
      )}
    </div>
  );
}

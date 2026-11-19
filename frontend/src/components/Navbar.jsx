import { useState, useEffect } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { Moon, Sun, User as UserIcon, LogOut, Terminal, Activity, Sparkles } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { useTheme } from '../context/ThemeContext';
import { getSystemHealth } from '../api/auth';
import { FixsemblyWordmark } from '../assets/logo';

export default function Navbar({ onOpenAuthModal }) {
  const { user, isGuest, guestName, logout, clearGuest } = useAuth();
  const { isDark, toggleTheme } = useTheme();
  const [backendOnline, setBackendOnline] = useState(false);
  const location = useLocation();

  useEffect(() => {
    getSystemHealth()
      .then((h) => setBackendOnline(h.status === 'ok'))
      .catch(() => setBackendOnline(false));

    const interval = setInterval(() => {
      getSystemHealth()
        .then((h) => setBackendOnline(h.status === 'ok'))
        .catch(() => setBackendOnline(false));
    }, 15000);

    return () => clearInterval(interval);
  }, []);

  return (
    <header className="sticky top-0 z-40 w-full border-b border-slate-200/80 dark:border-slate-800/80 bg-white/80 dark:bg-slate-950/80 backdrop-blur-md transition-colors duration-150">
      <div className="flex h-14 items-center justify-between px-4 sm:px-6">
        {/* Brand */}
        <div className="flex items-center gap-3">
          <Link to="/" className="group">
            <FixsemblyWordmark showTagline={true} />
          </Link>
        </div>

        {/* Center / Feature banner */}
        <div className="hidden md:flex items-center gap-2 text-xs font-mono text-slate-600 dark:text-slate-400 bg-slate-100 dark:bg-slate-900/90 px-3 py-1 rounded-full border border-slate-200 dark:border-slate-800">
          <span className="flex h-2 w-2 rounded-full bg-emerald-500 animate-pulse"></span>
          <span>Red to green, automatically</span>
        </div>

        {/* Actions */}
        <div className="flex items-center gap-3">
          {/* Health Pill */}
          <div
            className={`flex items-center gap-1.5 text-xs font-medium px-2.5 py-1 rounded-full border ${
              backendOnline
                ? 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20'
                : 'bg-rose-500/10 text-rose-600 dark:text-rose-400 border-rose-500/20'
            }`}
          >
            <span
              className={`h-1.5 w-1.5 rounded-full ${backendOnline ? 'bg-emerald-500' : 'bg-rose-500'}`}
            ></span>
            <span className="hidden sm:inline">{backendOnline ? 'API Online' : 'Connecting...'}</span>
          </div>

          {/* Theme Toggle */}
          <button
            onClick={toggleTheme}
            className="flex h-8 w-8 items-center justify-center rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-100 hover:border-slate-300 dark:hover:border-slate-700 shadow-sm transition"
            title={isDark ? "Switch to light mode" : "Switch to dark mode"}
            aria-label="Toggle theme"
          >
            {isDark ? <Sun className="h-4 w-4 text-amber-400" /> : <Moon className="h-4 w-4 text-slate-700" />}
          </button>

          {/* User / Guest Pill */}
          {user ? (
            <div className="flex items-center gap-2 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg p-1 pr-2.5 shadow-sm">
              <div className="h-6 w-6 rounded bg-brand-600/30 text-brand-600 dark:text-brand-300 flex items-center justify-center text-xs font-semibold">
                {user.nickname?.[0]?.toUpperCase() || user.email[0].toUpperCase()}
              </div>
              <span className="text-xs font-medium text-slate-800 dark:text-slate-200 max-w-[120px] truncate">
                {user.nickname || user.email}
              </span>
              <button
                onClick={logout}
                className="text-slate-400 hover:text-rose-500 transition ml-1"
                title="Log out"
              >
                <LogOut className="h-3.5 w-3.5" />
              </button>
            </div>
          ) : isGuest ? (
            <div className="flex items-center gap-2 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg p-1 pr-2.5 shadow-sm">
              <span className="text-[11px] uppercase tracking-wider px-1.5 py-0.5 rounded bg-indigo-500/15 text-indigo-600 dark:text-indigo-300 font-semibold">
                Guest
              </span>
              <span className="text-xs font-medium text-slate-800 dark:text-slate-200 max-w-[110px] truncate">
                {guestName}
              </span>
              <button
                onClick={clearGuest}
                className="text-slate-400 hover:text-amber-500 transition ml-1 text-xs"
                title="Exit guest mode"
              >
                Exit
              </button>
            </div>
          ) : (
            <button
              onClick={onOpenAuthModal}
              className="flex items-center gap-1.5 text-xs font-medium bg-brand-600 hover:bg-brand-500 text-white px-3 py-1.5 rounded-lg shadow-sm transition"
            >
              <UserIcon className="h-3.5 w-3.5" />
              <span>Sign In</span>
            </button>
          )}
        </div>
      </div>
    </header>
  );
}

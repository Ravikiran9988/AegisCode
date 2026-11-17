import { useState, useEffect } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { ShieldCheck, Moon, Sun, User as UserIcon, LogOut, Terminal, Activity } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { useTheme } from '../context/ThemeContext';
import { getSystemHealth } from '../api/auth';

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
    <header className="sticky top-0 z-40 w-full border-b border-slate-800/80 bg-slate-950/80 backdrop-blur-md">
      <div className="flex h-14 items-center justify-between px-4 sm:px-6">
        {/* Brand */}
        <div className="flex items-center gap-3">
          <Link to="/" className="flex items-center gap-2.5 group">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-gradient-to-tr from-brand-600 to-indigo-500 shadow-lg shadow-brand-500/25 group-hover:shadow-brand-500/40 transition">
              <ShieldCheck className="h-5 w-5 text-white" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-bold text-lg tracking-tight bg-gradient-to-r from-white via-slate-100 to-slate-300 bg-clip-text text-transparent">
                  Fixsembly
                </span>
                <span className="text-[10px] font-semibold uppercase tracking-wider px-1.5 py-0.5 rounded bg-brand-500/10 text-brand-400 border border-brand-500/20">
                  v2.0
                </span>
              </div>
              <p className="text-[11px] text-slate-400 hidden sm:block -mt-0.5">
                Three Agents. One Verified Fix.
              </p>
            </div>
          </Link>
        </div>

        {/* Center / Feature banner */}
        <div className="hidden md:flex items-center gap-2 text-xs font-mono text-slate-400 bg-slate-900/90 px-3 py-1 rounded-full border border-slate-800">
          <span className="flex h-2 w-2 rounded-full bg-emerald-500 animate-pulse"></span>
          <span>Red to green, automatically</span>
        </div>

        {/* Actions */}
        <div className="flex items-center gap-3">
          {/* Health Pill */}
          <div
            className={`flex items-center gap-1.5 text-xs font-medium px-2.5 py-1 rounded-full border ${
              backendOnline
                ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                : 'bg-rose-500/10 text-rose-400 border-rose-500/20'
            }`}
          >
            <span
              className={`h-1.5 w-1.5 rounded-full ${backendOnline ? 'bg-emerald-400' : 'bg-rose-400'}`}
            ></span>
            <span className="hidden sm:inline">{backendOnline ? 'Engine Online' : 'Connecting...'}</span>
          </div>

          {/* Theme Toggle */}
          <button
            onClick={toggleTheme}
            className="flex h-8 w-8 items-center justify-center rounded-lg border border-slate-800 bg-slate-900 text-slate-400 hover:text-slate-100 hover:border-slate-700 transition"
            title="Toggle theme"
          >
            {isDark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
          </button>

          {/* User / Guest Pill */}
          {user ? (
            <div className="flex items-center gap-2 bg-slate-900 border border-slate-800 rounded-lg p-1 pr-2.5">
              <div className="h-6 w-6 rounded bg-brand-600/30 text-brand-300 flex items-center justify-center text-xs font-semibold">
                {user.nickname?.[0]?.toUpperCase() || user.email[0].toUpperCase()}
              </div>
              <span className="text-xs font-medium text-slate-200 max-w-[120px] truncate">
                {user.nickname || user.email}
              </span>
              <button
                onClick={logout}
                className="text-slate-400 hover:text-rose-400 transition ml-1"
                title="Log out"
              >
                <LogOut className="h-3.5 w-3.5" />
              </button>
            </div>
          ) : isGuest ? (
            <div className="flex items-center gap-2 bg-slate-900 border border-slate-800 rounded-lg p-1 pr-2.5">
              <span className="text-[11px] uppercase tracking-wider px-1.5 py-0.5 rounded bg-indigo-500/20 text-indigo-300 font-semibold">
                Guest
              </span>
              <span className="text-xs font-medium text-slate-200 max-w-[110px] truncate">
                {guestName}
              </span>
              <button
                onClick={clearGuest}
                className="text-slate-400 hover:text-amber-400 transition ml-1 text-xs"
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

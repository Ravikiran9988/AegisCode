import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard,
  PlayCircle,
  Activity,
  History,
  HeartPulse,
  BookOpen,
  Cpu,
  Flame,
} from 'lucide-react';
import { FixsemblyIcon } from '../assets/logo';

const navigation = [
  { name: 'Control Center', to: '/overview', icon: LayoutDashboard },
  { name: 'New Repair', to: '/repair/new', icon: PlayCircle },
  { name: 'Active Repairs', to: '/repair/active', icon: Activity },
  { name: 'Repair History', to: '/history', icon: History },
  { name: 'System Health', to: '/health', icon: HeartPulse },
  { name: 'Architecture & Docs', to: '/docs', icon: BookOpen },
];

export default function Sidebar() {
  return (
    <aside className="w-60 flex-shrink-0 border-r border-slate-800/80 bg-slate-950/60 p-3 hidden md:flex flex-col justify-between">
      <div className="space-y-6">
        {/* Navigation Group */}
        <div>
          <p className="px-3 text-[11px] font-semibold uppercase tracking-wider text-slate-500 mb-2">
            Platform
          </p>
          <nav className="space-y-1">
            {navigation.map((item) => (
              <NavLink
                key={item.name}
                to={item.to}
                className={({ isActive }) =>
                  `flex items-center gap-3 px-3 py-2 text-xs font-medium rounded-lg transition ${
                    isActive
                      ? 'bg-brand-600/15 text-brand-600 dark:text-brand-300 border border-brand-500/25 shadow-sm font-semibold'
                      : 'text-slate-400 hover:text-slate-100 hover:bg-slate-900/60'
                  }`
                }
              >
                <item.icon className="h-4 w-4 flex-shrink-0" />
                <span>{item.name}</span>
              </NavLink>
            ))}
          </nav>
        </div>

        {/* Multi-Agent Architecture Card */}
        <div className="rounded-xl border border-slate-800/80 bg-slate-900/40 p-3 text-xs">
          <div className="flex items-center gap-2 text-slate-300 font-semibold mb-2">
            <FixsemblyIcon size={16} />
            <span>Agent Assembly</span>
          </div>
          <div className="space-y-2 text-[11px] text-slate-400">
            <div className="flex items-center justify-between">
              <span className="flex items-center gap-1.5">
                <span className="h-1.5 w-1.5 rounded-full bg-blue-400"></span>
                Architect
              </span>
              <span className="text-slate-500 font-mono">Plan</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="flex items-center gap-1.5">
                <span className="h-1.5 w-1.5 rounded-full bg-indigo-400"></span>
                Coder
              </span>
              <span className="text-slate-500 font-mono">Patch</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="flex items-center gap-1.5">
                <span className="h-1.5 w-1.5 rounded-full bg-amber-400"></span>
                Pytest
              </span>
              <span className="text-slate-500 font-mono">Verify</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="flex items-center gap-1.5">
                <span className="h-1.5 w-1.5 rounded-full bg-emerald-400"></span>
                Reviewer
              </span>
              <span className="text-slate-500 font-mono">Audit</span>
            </div>
          </div>
        </div>
      </div>

      {/* Footer Info */}
      <div className="pt-4 border-t border-slate-900 text-[11px] text-slate-500 font-mono flex items-center justify-between px-2">
        <span>LangGraph Orchestrated</span>
        <span className="text-emerald-500 flex items-center gap-1">
          <Flame className="h-3 w-3" /> Auto
        </span>
      </div>
    </aside>
  );
}

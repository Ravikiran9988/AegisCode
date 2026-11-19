export default function StatCard({ title, value, subtext, icon: Icon, trend = null, color = 'brand' }) {
  const colorMap = {
    brand: 'text-brand-600 dark:text-brand-400 bg-brand-500/10 border-brand-500/20',
    emerald: 'text-emerald-600 dark:text-emerald-400 bg-emerald-500/10 border-emerald-500/20',
    blue: 'text-blue-600 dark:text-blue-400 bg-blue-500/10 border-blue-500/20',
    amber: 'text-amber-600 dark:text-amber-400 bg-amber-500/10 border-amber-500/20',
  }[color] || 'text-brand-600 dark:text-brand-400 bg-brand-500/10 border-brand-500/20';

  return (
    <div className="rounded-2xl border border-slate-200 dark:border-slate-800/80 bg-white dark:bg-slate-900/60 p-4 shadow-sm backdrop-blur-sm relative overflow-hidden group hover:border-slate-300 dark:hover:border-slate-700/80 transition">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-xs font-medium text-slate-600 dark:text-slate-400 uppercase tracking-wider font-mono">
            {title}
          </p>
          <h4 className="text-2xl font-bold text-slate-900 dark:text-slate-100 mt-1 tracking-tight">
            {value}
          </h4>
        </div>
        <div className={`h-10 w-10 rounded-xl flex items-center justify-center border ${colorMap}`}>
          <Icon className="h-5 w-5" />
        </div>
      </div>
      {subtext && (
        <div className="mt-3 pt-2 border-t border-slate-100 dark:border-slate-800/60 flex items-center justify-between text-[11px] text-slate-600 dark:text-slate-400">
          <span>{subtext}</span>
          {trend && <span className="font-semibold text-emerald-600 dark:text-emerald-400">{trend}</span>}
        </div>
      )}
    </div>
  );
}

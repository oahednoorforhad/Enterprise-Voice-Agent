import { type LucideIcon } from 'lucide-react'

interface MetricCardProps {
  title: string
  value: string | number
  description?: string
  icon: LucideIcon
  trend?: { value: number; positive: boolean }
  color?: 'brand' | 'emerald' | 'amber' | 'rose' | 'violet'
  onClick?: () => void
}

const colorMap = {
  brand: {
    bg: 'bg-brand-50 dark:bg-brand-950/30',
    icon: 'text-brand-600 dark:text-brand-400',
    border: 'border-brand-200 dark:border-brand-800',
  },
  emerald: {
    bg: 'bg-emerald-50 dark:bg-emerald-950/30',
    icon: 'text-emerald-600 dark:text-emerald-400',
    border: 'border-emerald-200 dark:border-emerald-800',
  },
  amber: {
    bg: 'bg-amber-50 dark:bg-amber-950/30',
    icon: 'text-amber-600 dark:text-amber-400',
    border: 'border-amber-200 dark:border-amber-800',
  },
  rose: {
    bg: 'bg-rose-50 dark:bg-rose-950/30',
    icon: 'text-rose-600 dark:text-rose-400',
    border: 'border-rose-200 dark:border-rose-800',
  },
  violet: {
    bg: 'bg-violet-50 dark:bg-violet-950/30',
    icon: 'text-violet-600 dark:text-violet-400',
    border: 'border-violet-200 dark:border-violet-800',
  },
}

export default function MetricCard({
  title,
  value,
  description,
  icon: Icon,
  trend,
  color = 'brand',
  onClick,
}: MetricCardProps) {
  const c = colorMap[color]

  return (
    <div
      className={`card p-6 ${onClick ? 'cursor-pointer hover:scale-[1.02] active:scale-[0.98]' : ''} transition-all duration-200`}
      onClick={onClick}
      role={onClick ? 'button' : undefined}
      tabIndex={onClick ? 0 : undefined}
      onKeyDown={onClick ? (e) => { if (e.key === 'Enter' || e.key === ' ') onClick() } : undefined}
    >
      <div className="flex items-start justify-between mb-4">
        <div className={`p-2.5 rounded-lg ${c.bg} ${c.border} border`}>
          <Icon size={20} className={c.icon} />
        </div>
        {trend && (
          <span
            className={`inline-flex items-center gap-1 text-xs font-semibold px-2 py-0.5 rounded-full ${
              trend.positive
                ? 'text-emerald-600 bg-emerald-50 dark:text-emerald-400 dark:bg-emerald-950/30'
                : 'text-rose-600 bg-rose-50 dark:text-rose-400 dark:bg-rose-950/30'
            }`}
          >
            <svg
              width="10"
              height="10"
              viewBox="0 0 10 10"
              fill="none"
              className={trend.positive ? '' : 'rotate-180'}
            >
              <path
                d="M5 1.5L8.5 7H1.5L5 1.5Z"
                fill="currentColor"
              />
            </svg>
            {Math.abs(trend.value)}%
          </span>
        )}
      </div>
      <p className="metric-label mb-1">{title}</p>
      <p className="metric-value">{value}</p>
      {description && (
        <p className="text-xs text-gray-400 dark:text-gray-500 mt-1.5">
          {description}
        </p>
      )}
    </div>
  )
}

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
    icon: 'text-brand-coral',
  },
  emerald: {
    icon: 'text-green-500',
  },
  amber: {
    icon: 'text-amber-500',
  },
  rose: {
    icon: 'text-coral-400',
  },
  violet: {
    icon: 'text-brand-blue',
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
      className={`card-flat p-5 ${onClick ? 'cursor-pointer hover:border-ink/20 active:scale-[0.99]' : ''} transition-all duration-200`}
      onClick={onClick}
      role={onClick ? 'button' : undefined}
      tabIndex={onClick ? 0 : undefined}
      onKeyDown={onClick ? (e) => { if (e.key === 'Enter' || e.key === ' ') onClick() } : undefined}
    >
      <div className="flex items-start justify-between mb-4">
        <div className={`p-2.5 rounded-sm bg-surface-stone dark:bg-surface-dark-elevated`}>
          <Icon size={20} className={c.icon} />
        </div>
        {trend && (
          <span
            className={`inline-flex items-center gap-1 text-micro font-semibold px-2 py-0.5 rounded-pill ${
              trend.positive
                ? 'chip-green'
                : 'chip-red'
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
      <p className="label-mono text-[11px] mb-1">{title}</p>
      <p className="font-display text-display-product text-brand-near dark:text-white leading-none">{value}</p>
      {description && (
        <p className="text-caption text-muted-slate mt-1.5">{description}</p>
      )}
    </div>
  )
}

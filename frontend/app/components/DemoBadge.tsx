import { Link } from '@tanstack/react-router'
import { FlaskConical } from 'lucide-react'

export default function DemoBadge() {
  const scenarioName = typeof localStorage !== 'undefined'
    ? localStorage.getItem('active_scenario_name') ?? 'Demo'
    : 'Demo'

  return (
    <div className="rounded-xl bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-800 p-3">
      <div className="flex items-center gap-2 mb-2">
        <FlaskConical size={14} className="text-amber-600 dark:text-amber-400" />
        <span className="text-xs font-bold text-amber-700 dark:text-amber-400 uppercase tracking-wide">Demo Mode</span>
      </div>
      <p className="text-xs text-amber-600 dark:text-amber-500 mb-2 truncate">{scenarioName}</p>
      <Link
        to="/scenarios"
        className="text-xs text-amber-700 dark:text-amber-400 hover:underline font-medium"
      >
        Switch Persona →
      </Link>
    </div>
  )
}

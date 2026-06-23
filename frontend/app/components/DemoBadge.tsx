import { Link } from '@tanstack/react-router'
import { FlaskConical } from 'lucide-react'

export default function DemoBadge() {
  const scenarioName = typeof localStorage !== 'undefined'
    ? localStorage.getItem('active_scenario_name') ?? 'Demo'
    : 'Demo'

  return (
    <div className="demo-badge">
      <div className="flex items-center gap-2 mb-1.5">
        <FlaskConical size={14} className="text-coral-500" />
        <span className="label">Demo Mode</span>
      </div>
      <p className="text-caption text-coral-600 dark:text-coral-500 mb-1.5 truncate">{scenarioName}</p>
      <Link
        to="/scenarios"
        className="text-caption font-medium text-coral-700 dark:text-coral-400 hover:underline"
      >
        Switch Persona →
      </Link>
    </div>
  )
}

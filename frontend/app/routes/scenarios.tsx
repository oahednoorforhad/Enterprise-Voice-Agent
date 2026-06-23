import { useState } from 'react'
import { useNavigate } from '@tanstack/react-router'
import { useMutation } from '@tanstack/react-query'
import { api } from '../lib/api-client'
import { Sparkles, Loader2, FlaskConical } from 'lucide-react'

const SCENARIOS = [
  {
    id: 'billing_dispute',
    title: 'Billing Dispute',
    icon: '💰',
    description: 'Double-charged and overbilled — resolve urgent billing issues',
    color: 'from-red-500 to-orange-500',
  },
  {
    id: 'technical_bug',
    title: 'Technical Bug',
    icon: '🔧',
    description: 'SSO integration failure — diagnose and fix a critical system bug',
    color: 'from-purple-500 to-indigo-500',
  },
  {
    id: 'happy_upgrade',
    title: 'Happy Upgrade',
    icon: '⭐',
    description: 'Just upgraded to Enterprise — explore new plan capabilities',
    color: 'from-green-500 to-emerald-500',
  },
  {
    id: 'churn_risk',
    title: 'At-Risk Customer',
    icon: '⚠️',
    description: 'Customer considering cancellation — prevent churn with proactive support',
    color: 'from-amber-500 to-orange-500',
  },
  {
    id: 'new_onboarding',
    title: 'New Onboarding',
    icon: '🚀',
    description: 'Brand new customer — guide them through first-week experience',
    color: 'from-blue-500 to-cyan-500',
  },
]

function scenarioLabel(id: string): string {
  const map: Record<string, string> = {
    billing_dispute: 'Billing Dispute',
    technical_bug: 'Technical Bug',
    happy_upgrade: 'Happy Upgrade',
    churn_risk: 'At-Risk Customer',
    new_onboarding: 'New Onboarding',
  }
  return map[id] ?? id
}

export function ScenariosPage() {
  const navigate = useNavigate()
  const [selectedId, setSelectedId] = useState<string | null>(null)

  const applyMutation = useMutation({
    mutationFn: (scenarioId: string) => api.applyScenario(scenarioId),
    onSuccess: (_data, scenarioId) => {
      localStorage.setItem('active_scenario_name', scenarioLabel(scenarioId))
      navigate({ to: '/app/chat', replace: true })
    },
  })

  const handleSelect = (scenarioId: string) => {
    setSelectedId(scenarioId)
    applyMutation.mutate(scenarioId)
  }

  if (applyMutation.isPending) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-gray-900 via-gray-800 to-brand-900 flex flex-col items-center justify-center">
        <Loader2 size={48} className="text-brand-400 animate-spin mb-6" />
        <p className="text-white text-lg font-medium mb-2">Setting up your demo environment...</p>
        <p className="text-gray-400 text-sm">
          {selectedId && `Loading ${scenarioLabel(selectedId)} scenario`}
        </p>
      </div>
    )
  }

  if (applyMutation.isError) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-gray-900 via-gray-800 to-brand-900 flex flex-col items-center justify-center text-center px-8">
        <div className="max-w-md">
          <p className="text-red-400 text-lg font-medium mb-2">Failed to set up scenario</p>
          <p className="text-gray-400 text-sm mb-6">
            {applyMutation.error instanceof Error ? applyMutation.error.message : 'Something went wrong. Please try again.'}
          </p>
          <button
            onClick={() => { setSelectedId(null); applyMutation.reset() }}
            className="px-6 py-3 bg-white text-gray-900 font-semibold rounded-xl hover:bg-gray-100 transition-colors"
          >
            Try Again
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-900 via-gray-800 to-brand-900 flex flex-col">
      {/* Header */}
      <header className="px-8 py-6 flex items-center gap-3">
        <div className="w-9 h-9 rounded-xl bg-brand-600 flex items-center justify-center">
          <Sparkles size={20} className="text-white" />
        </div>
        <div>
          <span className="text-white font-bold text-lg">EVA</span>
          <span className="text-gray-400 text-sm ml-1">Demo Mode</span>
        </div>
      </header>

      {/* Content */}
      <main className="flex-1 flex flex-col items-center justify-center px-6 py-10">
        <div className="max-w-2xl text-center mb-12">
          <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-amber-500/10 border border-amber-500/20 text-amber-400 text-sm mb-6">
            <FlaskConical size={14} />
            Choose a scenario to preview your demo
          </div>
          <h1 className="text-4xl font-extrabold text-white mb-4">
            Try Enterprise Voice Agent
          </h1>
          <p className="text-gray-300 text-base">
            Select a situation below and we'll populate your account with realistic data
            so you can experience EVA firsthand.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5 max-w-4xl w-full">
          {SCENARIOS.map((scenario) => (
            <button
              key={scenario.id}
              onClick={() => handleSelect(scenario.id)}
              disabled={applyMutation.isPending}
              className="group relative text-left bg-white/5 hover:bg-white/10 border border-white/10 hover:border-white/20 rounded-2xl p-6 transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <div className={`w-12 h-12 rounded-xl bg-gradient-to-br ${scenario.color} flex items-center justify-center text-xl mb-4`}>
                {scenario.icon}
              </div>
              <h3 className="text-white font-semibold mb-1.5">{scenario.title}</h3>
              <p className="text-gray-400 text-sm leading-relaxed">{scenario.description}</p>
              <div className="mt-4 flex items-center gap-1.5 text-brand-400 text-sm font-medium opacity-0 group-hover:opacity-100 transition-opacity">
                <span>Select scenario</span>
                <span className="text-lg leading-none">→</span>
              </div>
            </button>
          ))}
        </div>
      </main>
    </div>
  )
}

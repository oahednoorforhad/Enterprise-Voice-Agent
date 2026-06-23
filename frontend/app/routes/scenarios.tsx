import { useState } from 'react'
import { useNavigate } from '@tanstack/react-router'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../lib/api-client'
import { Sparkles, Loader2, FlaskConical } from 'lucide-react'

const SCENARIOS = [
  {
    id: 'billing_dispute',
    title: 'Billing Dispute',
    icon: '💰',
    description: 'Double-charged and overbilled — resolve urgent billing issues',
    color: 'from-red-400 to-orange-400',
  },
  {
    id: 'technical_bug',
    title: 'Technical Bug',
    icon: '🔧',
    description: 'SSO integration failure — diagnose and fix a critical system bug',
    color: 'from-purple-400 to-indigo-400',
  },
  {
    id: 'happy_upgrade',
    title: 'Happy Upgrade',
    icon: '⭐',
    description: 'Just upgraded to Enterprise — explore new plan capabilities',
    color: 'from-green-400 to-emerald-400',
  },
  {
    id: 'churn_risk',
    title: 'At-Risk Customer',
    icon: '⚠️',
    description: 'Customer considering cancellation — prevent churn with proactive support',
    color: 'from-amber-400 to-orange-400',
  },
  {
    id: 'new_onboarding',
    title: 'New Onboarding',
    icon: '🚀',
    description: 'Brand new customer — guide them through first-week experience',
    color: 'from-blue-400 to-cyan-400',
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
  const queryClient = useQueryClient()

  const applyMutation = useMutation({
    mutationFn: (scenarioId: string) => api.applyScenario(scenarioId),
    onSuccess: (_data, scenarioId) => {
      localStorage.setItem('active_scenario_name', scenarioLabel(scenarioId))
      queryClient.invalidateQueries()
      navigate({ to: '/app/chat', replace: true })
    },
  })

  const handleSelect = (scenarioId: string) => {
    setSelectedId(scenarioId)
    applyMutation.mutate(scenarioId)
  }

  if (applyMutation.isPending) {
    return (
      <div className="min-h-screen bg-surface-white dark:bg-surface-dark flex flex-col items-center justify-center">
        <Loader2 size={48} className="text-brand-coral animate-spin mb-6" />
        <p className="text-heading-feature font-display text-ink dark:text-white mb-2">Setting up your demo environment...</p>
        <p className="text-caption text-muted-slate">
          {selectedId && `Loading ${scenarioLabel(selectedId)} scenario`}
        </p>
      </div>
    )
  }

  if (applyMutation.isError) {
    return (
      <div className="min-h-screen bg-surface-white dark:bg-surface-dark flex flex-col items-center justify-center text-center px-8">
        <div className="max-w-md">
          <p className="text-heading-feature font-display text-red-600 dark:text-red-400 mb-2">Failed to set up scenario</p>
          <p className="text-caption text-muted-slate mb-6">
            {applyMutation.error instanceof Error ? applyMutation.error.message : 'Something went wrong. Please try again.'}
          </p>
          <button
            onClick={() => { setSelectedId(null); applyMutation.reset() }}
            className="btn-pill-primary"
          >
            Try Again
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-surface-white dark:bg-surface-dark flex flex-col">
      {/* Near-black header band */}
      <header className="band-dark px-8 py-5">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-sm bg-white/10 flex items-center justify-center">
            <Sparkles size={16} className="text-coral-400" />
          </div>
          <div>
            <span className="font-display text-heading-feature text-white">EVA</span>
            <span className="label-mono text-coral-300 ml-2">Demo Mode</span>
          </div>
        </div>
      </header>

      {/* Content */}
      <main className="flex-1 flex flex-col items-center justify-center px-6 py-16">
        <div className="max-w-2xl text-center mb-12 animate-stagger-1">
          <div className="chip-coral inline-flex items-center gap-2 mb-6">
            <FlaskConical size={14} />
            Choose a scenario to preview your demo
          </div>
          <h1 className="heading-hero text-ink dark:text-white mb-4">
            Try Enterprise Voice Agent
          </h1>
          <p className="text-body-large text-muted-slate">
            Select a situation below and we'll populate your account with realistic data
            so you can experience EVA firsthand.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 max-w-3xl w-full">
          {SCENARIOS.map((scenario, idx) => {
            const isHero = scenario.id === 'billing_dispute'
            return (
              <button
                key={scenario.id}
                onClick={() => handleSelect(scenario.id)}
                disabled={applyMutation.isPending}
                className={`group relative text-left card-flat hover:border-ink/30 dark:hover:border-gray-500/30 p-4 transition-all duration-200 hover:shadow-sm active:scale-[0.99] disabled:opacity-50 disabled:cursor-not-allowed ${isHero ? 'md:row-span-2' : ''} animate-stagger-${Math.min(idx + 2, 5)}`}
              >
                <div className="flex items-start gap-3">
                  <div className={`w-10 h-10 rounded-sm bg-surface-stone dark:bg-surface-dark-elevated flex items-center justify-center flex-shrink-0 text-lg ${isHero ? 'w-12 h-12 text-xl' : ''}`}>
                    {scenario.icon}
                  </div>
                  <div className="min-w-0">
                    <h3 className={`font-display text-ink dark:text-white font-medium truncate ${isHero ? 'text-heading-feature' : 'text-body-small font-semibold'}`}>
                      {scenario.title}
                    </h3>
                    <p className="text-caption text-muted-slate leading-relaxed mt-0.5">{scenario.description}</p>
                    <div className="flex items-center gap-1 text-brand-coral text-caption font-medium opacity-0 group-hover:opacity-100 transition-opacity mt-2">
                      <span>Select</span>
                      <span className="text-xs leading-none">→</span>
                    </div>
                  </div>
                </div>
              </button>
            )
          })}
        </div>
      </main>
    </div>
  )
}

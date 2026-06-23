import { Check, X, Loader2, Brain, Wrench, Zap } from 'lucide-react'

const TOOL_LABELS: Record<string, string> = {
  get_customer_profile: 'Customer Profile',
  get_subscription_status: 'Subscription',
  get_billing_history: 'Billing History',
  get_support_tickets: 'Support Tickets',
  get_ticket_status: 'Ticket Status',
  get_usage_analytics: 'Usage Analytics',
  search_documentation: 'Documentation',
  search_policies: 'Policies',
}

export type ThinkingStep =
  | { type: 'thinking' }
  | { type: 'intent'; label: string }
  | { type: 'tools_selected'; tools: string[]; replan?: boolean }
  | { type: 'tool_done'; tool: string; ok: boolean }
  | { type: 'reasoning' }

interface ThinkingPanelProps {
  steps: ThinkingStep[]
  isStreaming: boolean
}

export default function ThinkingPanel({ steps, isStreaming }: ThinkingPanelProps) {
  if (steps.length === 0) return null

  const isThinkingOnly = steps.length === 1 && steps[0].type === 'thinking'

  const intentStep = steps.find((s) => s.type === 'intent') as
    | { type: 'intent'; label: string }
    | undefined

  const selectedTools: string[] = []
  for (const step of steps) {
    if (step.type === 'tools_selected') {
      for (const t of step.tools) {
        if (!selectedTools.includes(t)) selectedTools.push(t)
      }
    }
  }

  const toolDoneMap: Record<string, boolean> = {}
  for (const step of steps) {
    if (step.type === 'tool_done') {
      toolDoneMap[step.tool] = step.ok
    }
  }

  const hasReasoning = steps.some((s) => s.type === 'reasoning')
  const visibleTools = selectedTools.filter((t) => t in toolDoneMap)
  const pendingTool = selectedTools.find((t) => !(t in toolDoneMap))
  const intentDone = selectedTools.length > 0 || hasReasoning
  const intentSpinning = isStreaming && !intentDone

  if (isThinkingOnly) {
    return (
      <div className="flex gap-3 animate-fade-in">
        <div className="flex-shrink-0 w-8 h-8 rounded-full bg-surface-stone dark:bg-surface-dark-elevated flex items-center justify-center">
          <Brain size={15} className="text-brand-coral" />
        </div>
        <div className="flex items-center gap-2 px-4 py-3 card-flat">
          <Loader2 size={13} className="text-brand-coral animate-spin flex-shrink-0" />
          <span className="text-caption text-muted-slate dark:text-gray-400">Thinking…</span>
        </div>
      </div>
    )
  }

  return (
    <div className="flex gap-3 animate-fade-in">
      <div className="flex-shrink-0 w-8 h-8 rounded-full bg-surface-stone dark:bg-surface-dark-elevated flex items-center justify-center">
        <Brain size={15} className="text-brand-coral" />
      </div>

      <div className="flex-1 max-w-[80%]">
        <div className="card-flat px-4 py-3 space-y-2.5">

          {intentStep && (
            <Row
              icon={<Zap size={13} className="text-brand-coral" />}
              label={intentStep.label}
              status={intentSpinning ? 'spinning' : 'done'}
            />
          )}

          {visibleTools.map((tool) => (
            <Row
              key={tool}
              icon={<Wrench size={13} className="text-muted-slate" />}
              label={TOOL_LABELS[tool] ?? tool}
              status={toolDoneMap[tool] ? 'done' : 'error'}
              chip
            />
          ))}

          {pendingTool && !hasReasoning && (
            <Row
              key={pendingTool}
              icon={<Wrench size={13} className="text-muted-slate" />}
              label={TOOL_LABELS[pendingTool] ?? pendingTool}
              status="spinning"
              chip
            />
          )}

          {hasReasoning && (
            <Row
              icon={<Brain size={13} className="text-brand-coral" />}
              label="Composing response…"
              status={isStreaming ? 'spinning' : 'done'}
            />
          )}
        </div>
      </div>
    </div>
  )
}

type RowStatus = 'spinning' | 'done' | 'error'

function Row({
  icon,
  label,
  status,
  chip = false,
}: {
  icon: React.ReactNode
  label: string
  status: RowStatus
  chip?: boolean
}) {
  return (
    <div className="flex items-center gap-2 animate-fade-in">
      <span className="flex-shrink-0 opacity-60">{icon}</span>
      <span
        className={`text-caption flex-1 ${
          chip
            ? 'font-mono text-[11px] text-muted-slate dark:text-gray-400'
            : 'text-ink dark:text-gray-200'
        }`}
      >
        {label}
      </span>
      <span className="flex-shrink-0 ml-auto">
        {status === 'spinning' && (
          <Loader2 size={13} className="text-brand-coral animate-spin" />
        )}
        {status === 'done' && (
          <Check size={13} className="text-green-500 dark:text-green-400" />
        )}
        {status === 'error' && (
          <X size={13} className="text-red-500 dark:text-red-400" />
        )}
      </span>
    </div>
  )
}

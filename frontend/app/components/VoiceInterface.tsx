/**
 * VoiceInterface — EVA voice call UI component.
 *
 * Renders the mic button, live transcript, active tool badges,
 * and post-call summary panel, using the Cohere-inspired design system.
 */

import { useCallback } from 'react'
import { Mic, MicOff, Phone, PhoneOff, Loader2, CheckCircle, AlertCircle } from 'lucide-react'
import { useVoiceSession, type VoiceState, type TranscriptLine } from '../hooks/useVoiceSession'
import { api } from '../lib/api-client'
import { useQuery } from '@tanstack/react-query'

const CUSTOMER_ID = 'c63d2f89-9aa3-4157-8205-a7d6cfc23207'

// ── Tool badge display names ─────────────────────────────────────────────────

const TOOL_LABELS: Record<string, string> = {
  get_customer_profile: 'Profile',
  get_subscription_status: 'Subscription',
  get_billing_history: 'Billing',
  get_support_tickets: 'Tickets',
  get_ticket_status: 'Ticket Status',
  get_usage_analytics: 'Usage',
  search_documentation: 'Docs',
  search_policies: 'Policies',
}

// ── Sub-components ───────────────────────────────────────────────────────────

function StateIndicator({ state }: { state: VoiceState }) {
  const labels: Record<VoiceState, string> = {
    idle: 'Ready',
    connecting: 'Connecting…',
    active: 'Listening',
    ending: 'Ending call…',
    ended: 'Call ended',
    error: 'Error',
  }
  const colors: Record<VoiceState, string> = {
    idle: 'text-muted-slate',
    connecting: 'text-amber-600 dark:text-amber-400',
    active: 'text-green-600 dark:text-green-400',
    ending: 'text-orange-600 dark:text-orange-400',
    ended: 'text-muted-slate',
    error: 'text-red-600 dark:text-red-400',
  }
  return (
    <span className={`text-body-small font-medium ${colors[state]}`}>{labels[state]}</span>
  )
}

function MicButton({
  state,
  onStart,
  onStop,
}: {
  state: VoiceState
  onStart: () => void
  onStop: () => void
}) {
  const isActive = state === 'active'
  const isLoading = state === 'connecting' || state === 'ending'
  const isEnded = state === 'ended' || state === 'idle' || state === 'error'

  return (
    <button
      onClick={isActive ? onStop : onStart}
      disabled={isLoading}
      aria-label={isActive ? 'End call' : 'Start call'}
      className={[
        'relative w-24 h-24 rounded-full flex items-center justify-center',
        'transition-all duration-300 focus:outline-none focus:ring-2 focus:ring-focus focus:ring-offset-2',
        isActive
          ? 'bg-brand-coral hover:bg-coral-600'
          : isLoading
          ? 'bg-muted-slate cursor-not-allowed'
          : 'bg-brand-near hover:bg-black dark:bg-white/10 dark:hover:bg-white/20',
      ].join(' ')}
    >
      {isLoading ? (
        <Loader2 size={36} className="text-white animate-spin" />
      ) : isActive ? (
        <PhoneOff size={36} className="text-white" />
      ) : (
        <Mic size={36} className="text-white" />
      )}
      {/* Pulsing ring when active */}
      {isActive && (
        <span className="absolute inset-0 rounded-full bg-coral-400 opacity-30 animate-ping" />
      )}
    </button>
  )
}

function ActiveToolBadges({ tools }: { tools: string[] }) {
  if (tools.length === 0) return null
  return (
    <div className="flex flex-wrap gap-2 justify-center">
      {tools.map((t) => (
        <span
          key={t}
          className="chip-coral text-[12px]"
        >
          {TOOL_LABELS[t] ?? t}
        </span>
      ))}
    </div>
  )
}

function TranscriptPanel({ lines }: { lines: TranscriptLine[] }) {
  if (lines.length === 0) return null
  return (
    <div className="w-full max-w-xl mt-4 card-flat overflow-hidden">
      <div className="px-4 py-2.5 border-b border-hairline dark:border-white/5">
        <span className="label-mono text-[11px]">Transcript</span>
      </div>
      <div className="max-h-64 overflow-y-auto px-4 py-3 space-y-2 scrollbar-thin">
        {lines.map((line, i) => (
          <div
            key={i}
            className={`flex gap-2 ${line.role === 'assistant' ? 'justify-start' : 'justify-end'}`}
          >
            <div
              className={[
                'max-w-[85%] px-3 py-2 text-body-small',
                line.role === 'assistant'
                  ? 'bg-surface-stone dark:bg-white/5 text-ink dark:text-gray-100 rounded-lg rounded-tl-sm'
                  : 'bg-brand-near dark:bg-white dark:text-ink text-white rounded-lg rounded-tr-sm',
              ].join(' ')}
            >
              {line.text}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

function CallSummaryPanel({ sessionId }: { sessionId: string }) {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['voice-summary', sessionId],
    queryFn: async () => {
      const base = typeof process !== 'undefined' && process.env?.VITE_API_URL
        ? process.env.VITE_API_URL
        : 'http://localhost:8000'
      const res = await fetch(`${base}/api/v1/voice/summary/${sessionId}`)
      if (!res.ok) throw new Error('Summary not ready')
      return res.json()
    },
    retry: 8,
    retryDelay: (attempt) => Math.min(2000 * 2 ** attempt, 8000),
    enabled: !!sessionId,
  })

  if (isLoading) {
    return (
      <div className="w-full max-w-xl mt-4 p-4 card-flat flex items-center gap-2 text-caption text-muted-slate">
        <Loader2 size={16} className="animate-spin" />
        Generating call summary…
      </div>
    )
  }

  if (isError || !data) return null

  return (
    <div className="w-full max-w-xl mt-4 card-flat border-green-200 dark:border-green-800 overflow-hidden">
      <div className="px-4 py-2.5 border-b border-green-100 dark:border-green-800 flex items-center gap-2">
        <CheckCircle size={14} className="text-green-600 dark:text-green-400" />
        <span className="label-mono text-[11px] text-green-700 dark:text-green-400">Call Summary</span>
      </div>
      <div className="px-4 py-3 space-y-3 text-body-small">
        <p className="text-ink dark:text-gray-300">{data.conversation_summary}</p>

        {data.sources_used?.length > 0 && (
          <div>
            <span className="label-mono text-[11px] mb-1 block">Sources consulted:</span>
            <div className="flex flex-wrap gap-1">
              {data.sources_used.map((s: string) => (
                <span key={s} className="chip-gray text-[12px]">
                  {TOOL_LABELS[s] ?? s}
                </span>
              ))}
            </div>
          </div>
        )}

        {data.recommended_next_actions?.length > 0 && (
          <div>
            <span className="label-mono text-[11px] mb-1 block">Recommended next steps:</span>
            <ul className="space-y-1 list-disc list-inside text-caption text-muted-slate">
              {data.recommended_next_actions.map((action: string, i: number) => (
                <li key={i}>{action}</li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  )
}

// ── Main component ────────────────────────────────────────────────────────────

export default function VoiceInterface() {
  const {
    state,
    sessionId,
    transcript,
    activeTools,
    error,
    startSession,
    stopSession,
    interrupt,
  } = useVoiceSession()

  const handleStart = useCallback(() => {
    void startSession(CUSTOMER_ID)
  }, [startSession])

  return (
    <div className="flex flex-col items-center gap-6 py-8 px-4">
      {/* Header */}
      <div className="text-center">
        <h2 className="font-display text-heading-card text-ink dark:text-white">
          EVA Voice Assistant
        </h2>
        <p className="mt-1 text-caption text-muted-slate">
          Speak naturally — EVA can look up your billing, tickets, and more.
        </p>
      </div>

      {/* Status */}
      <StateIndicator state={state} />

      {/* Mic button */}
      <MicButton state={state} onStart={handleStart} onStop={stopSession} />

      {/* Active tool indicators */}
      <ActiveToolBadges tools={activeTools} />

      {/* Interrupt button */}
      {state === 'active' && (
        <button
          onClick={interrupt}
          className="text-caption text-muted-slate hover:text-ink dark:hover:text-gray-300 underline underline-offset-2 transition-colors"
        >
          Stop speaking
        </button>
      )}

      {/* Error message */}
      {error && (
        <div className="flex items-center gap-2 px-4 py-2 rounded-lg chip-red">
          <AlertCircle size={16} />
          {error}
        </div>
      )}

      {/* Transcript */}
      <TranscriptPanel lines={transcript} />

      {/* Call summary (shown after session ends) */}
      {(state === 'ended') && sessionId && (
        <CallSummaryPanel sessionId={sessionId} />
      )}
    </div>
  )
}

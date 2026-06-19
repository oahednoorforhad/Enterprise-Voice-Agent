/**
 * VoiceInterface — EVA voice call UI component.
 *
 * Renders the mic button, live transcript, active tool badges,
 * and post-call summary panel.
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
    idle: 'text-gray-500 dark:text-gray-400',
    connecting: 'text-yellow-600 dark:text-yellow-400',
    active: 'text-green-600 dark:text-green-400',
    ending: 'text-orange-500 dark:text-orange-400',
    ended: 'text-gray-500 dark:text-gray-400',
    error: 'text-red-600 dark:text-red-400',
  }
  return (
    <span className={`text-sm font-medium ${colors[state]}`}>{labels[state]}</span>
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
        'transition-all duration-300 shadow-lg focus:outline-none focus:ring-4',
        isActive
          ? 'bg-red-500 hover:bg-red-600 focus:ring-red-300 dark:focus:ring-red-800'
          : isLoading
          ? 'bg-gray-400 dark:bg-gray-600 cursor-not-allowed'
          : 'bg-brand-600 hover:bg-brand-700 focus:ring-brand-300 dark:focus:ring-brand-800',
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
        <span className="absolute inset-0 rounded-full bg-red-500 opacity-30 animate-ping" />
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
          className="flex items-center gap-1 px-3 py-1 rounded-full text-xs font-medium
                     bg-brand-100 dark:bg-brand-900/40 text-brand-700 dark:text-brand-300
                     border border-brand-200 dark:border-brand-700"
        >
          <Loader2 size={12} className="animate-spin" />
          {TOOL_LABELS[t] ?? t}
        </span>
      ))}
    </div>
  )
}

function TranscriptPanel({ lines }: { lines: TranscriptLine[] }) {
  if (lines.length === 0) return null
  return (
    <div className="w-full max-w-xl mt-4 rounded-xl border border-gray-200 dark:border-gray-700
                    bg-white dark:bg-gray-800 overflow-hidden">
      <div className="px-4 py-2 border-b border-gray-100 dark:border-gray-700">
        <span className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide">
          Transcript
        </span>
      </div>
      <div className="max-h-64 overflow-y-auto px-4 py-3 space-y-2 scrollbar-thin">
        {lines.map((line, i) => (
          <div
            key={i}
            className={`flex gap-2 ${line.role === 'assistant' ? 'justify-start' : 'justify-end'}`}
          >
            <div
              className={[
                'max-w-[85%] px-3 py-2 rounded-2xl text-sm',
                line.role === 'assistant'
                  ? 'bg-gray-100 dark:bg-gray-700 text-gray-800 dark:text-gray-200 rounded-tl-sm'
                  : 'bg-brand-600 text-white rounded-tr-sm',
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
    // LLM summary generation can take 5–15 s; retry with exponential backoff.
    retry: 8,
    retryDelay: (attempt) => Math.min(2000 * 2 ** attempt, 8000),
    enabled: !!sessionId,
  })

  if (isLoading) {
    return (
      <div className="w-full max-w-xl mt-4 p-4 rounded-xl border border-gray-200 dark:border-gray-700
                      bg-white dark:bg-gray-800 flex items-center gap-2 text-sm text-gray-500">
        <Loader2 size={16} className="animate-spin" />
        Generating call summary…
      </div>
    )
  }

  if (isError || !data) return null

  return (
    <div className="w-full max-w-xl mt-4 rounded-xl border border-green-200 dark:border-green-700
                    bg-white dark:bg-gray-800 overflow-hidden">
      <div className="px-4 py-2 border-b border-green-100 dark:border-green-800 flex items-center gap-2">
        <CheckCircle size={14} className="text-green-600 dark:text-green-400" />
        <span className="text-xs font-semibold text-green-700 dark:text-green-400 uppercase tracking-wide">
          Call Summary
        </span>
      </div>
      <div className="px-4 py-3 space-y-3 text-sm">
        <p className="text-gray-700 dark:text-gray-300">{data.conversation_summary}</p>

        {data.sources_used?.length > 0 && (
          <div>
            <span className="text-xs font-semibold text-gray-500 dark:text-gray-400">
              Sources consulted:
            </span>
            <div className="flex flex-wrap gap-1 mt-1">
              {data.sources_used.map((s: string) => (
                <span
                  key={s}
                  className="px-2 py-0.5 rounded text-xs bg-gray-100 dark:bg-gray-700
                             text-gray-600 dark:text-gray-300"
                >
                  {TOOL_LABELS[s] ?? s}
                </span>
              ))}
            </div>
          </div>
        )}

        {data.recommended_next_actions?.length > 0 && (
          <div>
            <span className="text-xs font-semibold text-gray-500 dark:text-gray-400">
              Recommended next steps:
            </span>
            <ul className="mt-1 space-y-1 list-disc list-inside text-gray-600 dark:text-gray-400">
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
        <h2 className="text-2xl font-bold text-gray-900 dark:text-gray-100">
          EVA Voice Assistant
        </h2>
        <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
          Speak naturally — EVA can look up your billing, tickets, and more.
        </p>
      </div>

      {/* Status */}
      <StateIndicator state={state} />

      {/* Mic button */}
      <MicButton state={state} onStart={handleStart} onStop={stopSession} />

      {/* Active tool indicators */}
      <ActiveToolBadges tools={activeTools} />

      {/* Interrupt button (only shown while active) */}
      {state === 'active' && (
        <button
          onClick={interrupt}
          className="text-xs text-gray-400 hover:text-gray-600 dark:hover:text-gray-300
                     underline underline-offset-2 transition-colors"
        >
          Stop speaking
        </button>
      )}

      {/* Error message */}
      {error && (
        <div className="flex items-center gap-2 px-4 py-2 rounded-lg bg-red-50 dark:bg-red-900/20
                        border border-red-200 dark:border-red-800 text-sm text-red-700 dark:text-red-400">
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

/**
 * useVoiceSession — WebSocket + AudioContext state machine for EVA voice calls.
 *
 * State machine:
 *   idle → connecting → active → ending → ended
 *                    ↘ error
 *
 * The hook owns:
 *   - The WebSocket connection to /api/v1/voice/stream
 *   - The AudioWorklet mic resampler (48kHz→24kHz PCM capture)
 *   - The AudioContext used for Gemini audio playback
 *
 * No live Gemini API dependency — all network calls go to the FastAPI backend.
 */

import { useCallback, useEffect, useRef, useState } from 'react'
import {
  cancelScheduledAudio,
  createResampler,
  decodePCMFromBase64,
  encodePCMToBase64,
  schedulePlayback,
  type ResamplerHandle,
} from '../lib/audio-worklet'

// ── Types ───────────────────────────────────────────────────────────────────

export type VoiceState = 'idle' | 'connecting' | 'active' | 'ending' | 'ended' | 'error'

export interface TranscriptLine {
  role: 'user' | 'assistant'
  text: string
}

export interface ToolEvent {
  toolName: string
  status: 'calling' | 'done'
  timestamp: number
}

export interface UseVoiceSessionReturn {
  state: VoiceState
  sessionId: string | null
  transcript: TranscriptLine[]
  /** Tool names currently in-flight (status = "calling"). */
  activeTools: string[]
  /** Full tool history for the session. */
  toolHistory: ToolEvent[]
  error: string | null
  /** Start a voice call for the given customer. */
  startSession: (customerId: string) => Promise<void>
  /** Gracefully end the call. */
  stopSession: () => void
  /** Signal EVA to stop speaking (user interruption). */
  interrupt: () => void
}

// ── Constants ────────────────────────────────────────────────────────────────

const API_BASE = typeof process !== 'undefined' && process.env?.VITE_API_URL
  ? process.env.VITE_API_URL
  : 'http://localhost:8000'

const WS_BASE = API_BASE.replace(/^http/, 'ws')

// ── Hook ─────────────────────────────────────────────────────────────────────

export function useVoiceSession(): UseVoiceSessionReturn {
  const [state, setState] = useState<VoiceState>('idle')
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [transcript, setTranscript] = useState<TranscriptLine[]>([])
  const [activeTools, setActiveTools] = useState<string[]>([])
  const [toolHistory, setToolHistory] = useState<ToolEvent[]>([])
  const [error, setError] = useState<string | null>(null)

  const wsRef = useRef<WebSocket | null>(null)
  const resamplerRef = useRef<ResamplerHandle | null>(null)
  const playbackCtxRef = useRef<AudioContext | null>(null)
  const playbackTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  // Track state in a ref so event handlers always see the latest value
  const stateRef = useRef<VoiceState>('idle')

  const updateState = useCallback((s: VoiceState) => {
    stateRef.current = s
    setState(s)
  }, [])

  // Cleanup helper
  const cleanup = useCallback(() => {
    resamplerRef.current?.stop()
    resamplerRef.current = null
    if (playbackCtxRef.current && playbackCtxRef.current.state !== 'closed') {
      void playbackCtxRef.current.close()
    }
    playbackCtxRef.current = null
  }, [])

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      wsRef.current?.close()
      cleanup()
    }
  }, [cleanup])

  // ── Server event handler ─────────────────────────────────────────────────

  const handleServerEvent = useCallback((raw: string) => {
    let event: Record<string, unknown>
    try {
      event = JSON.parse(raw)
    } catch {
      return
    }

    const type = event.type as string

    switch (type) {
      case 'session_started': {
        setSessionId(event.session_id as string)
        updateState('active')
        break
      }

      case 'audio_chunk': {
        const b64 = event.data as string | undefined
        if (b64 && playbackCtxRef.current) {
          try {
            const pcm = decodePCMFromBase64(b64)
            schedulePlayback(playbackCtxRef.current, pcm)
          } catch {
            // malformed audio — ignore
          }
        }
        break
      }

      case 'generation_complete': {
        const ctx = playbackCtxRef.current
        if (ctx && wsRef.current) {
          const ctxWithCursor = ctx as AudioContext & { _playAt?: number }
          const remainingMs = Math.max(0, ((ctxWithCursor._playAt ?? 0) - ctx.currentTime) * 1000)
          const ws = wsRef.current
          playbackTimerRef.current = setTimeout(() => {
            playbackTimerRef.current = null
            if (ws.readyState === WebSocket.OPEN) {
              ws.send(JSON.stringify({ type: 'playback_complete' }))
            }
          }, remainingMs + 80)
        }
        break
      }

      case 'interrupted': {
        // Gemini cut itself off because user started speaking.
        // Cancel the playback_complete timer (no longer relevant) and
        // stop any audio still queued in the Web Audio scheduler.
        if (playbackTimerRef.current !== null) {
          clearTimeout(playbackTimerRef.current)
          playbackTimerRef.current = null
        }
        if (playbackCtxRef.current) {
          cancelScheduledAudio(playbackCtxRef.current)
        }
        break
      }

      case 'transcript': {
        const role = event.role as 'user' | 'assistant'
        const text = event.text as string
        if (text) {
          setTranscript((prev) => {
            const last = prev[prev.length - 1]
            // Append to the last bubble if it's the same role (streaming chunks).
            if (last && last.role === role) {
              return [...prev.slice(0, -1), { role, text: last.text + text }]
            }
            return [...prev, { role, text }]
          })
        }
        break
      }

      case 'tool_call': {
        const toolName = event.tool_name as string
        const status = event.status as 'calling' | 'done'
        const ts = Date.now()

        setToolHistory((prev) => [...prev, { toolName, status, timestamp: ts }])

        if (status === 'calling') {
          setActiveTools((prev) =>
            prev.includes(toolName) ? prev : [...prev, toolName],
          )
        } else if (status === 'done') {
          setActiveTools((prev) => prev.filter((n) => n !== toolName))
        }
        break
      }

      case 'session_ended': {
        updateState('ended')
        cleanup()
        break
      }

      case 'error': {
        setError(event.message as string)
        updateState('error')
        cleanup()
        break
      }

      default:
        break
    }
  }, [updateState, cleanup])

  // ── Public API ────────────────────────────────────────────────────────────

  const startSession = useCallback(async (customerId: string): Promise<void> => {
    if (stateRef.current !== 'idle' && stateRef.current !== 'ended' && stateRef.current !== 'error') {
      return
    }

    // Reset state
    updateState('connecting')
    setTranscript([])
    setActiveTools([])
    setToolHistory([])
    setSessionId(null)
    setError(null)

    // Open a fresh playback context (cursor starts at 0 implicitly).
    playbackCtxRef.current = new AudioContext({ sampleRate: 24_000 })

    const wsUrl = `${WS_BASE}/api/v1/voice/stream?customer_id=${encodeURIComponent(customerId)}&token=mock`
    const ws = new WebSocket(wsUrl)
    wsRef.current = ws

    ws.onopen = async () => {
      try {
        resamplerRef.current = await createResampler((pcm: Int16Array) => {
          if (ws.readyState === WebSocket.OPEN) {
            const b64 = encodePCMToBase64(pcm)
            ws.send(JSON.stringify({ type: 'audio_chunk', data: b64 }))
          }
        })
      } catch (err) {
        const msg = err instanceof Error ? err.message : 'Microphone access denied'
        setError(msg)
        updateState('error')
        ws.close()
      }
    }

    ws.onmessage = (ev: MessageEvent<string>) => {
      handleServerEvent(ev.data)
    }

    ws.onclose = () => {
      // Transition to ended from any non-terminal state
      if (stateRef.current === 'active' || stateRef.current === 'connecting' || stateRef.current === 'ending') {
        updateState('ended')
      }
      cleanup()
    }

    ws.onerror = () => {
      setError('WebSocket connection failed — is the backend running?')
      updateState('error')
      cleanup()
    }
  }, [updateState, cleanup, handleServerEvent])

  const stopSession = useCallback((): void => {
    updateState('ending')
    const ws = wsRef.current
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'end_of_audio' }))
      ws.close(1000, 'User ended call')
    }
    resamplerRef.current?.stop()
    resamplerRef.current = null
  }, [updateState])

  const interrupt = useCallback((): void => {
    if (playbackTimerRef.current !== null) {
      clearTimeout(playbackTimerRef.current)
      playbackTimerRef.current = null
    }
    if (playbackCtxRef.current) {
      cancelScheduledAudio(playbackCtxRef.current)
    }
    const ws = wsRef.current
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'interrupt' }))
    }
  }, [])

  return {
    state,
    sessionId,
    transcript,
    activeTools,
    toolHistory,
    error,
    startSession,
    stopSession,
    interrupt,
  }
}

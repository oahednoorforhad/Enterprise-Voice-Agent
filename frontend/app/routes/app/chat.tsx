import { useState, useRef, useEffect, useCallback, type Dispatch, type SetStateAction } from 'react'
import { Send, Sparkles, AlertCircle } from 'lucide-react'
import { useQueryClient } from '@tanstack/react-query'
import { Link, useParams } from '@tanstack/react-router'
import ChatMessage, { type Message } from '../../components/ChatMessage'
import ThinkingPanel, { type ThinkingStep } from '../../components/ThinkingPanel'
import { api, mock } from '../../lib/api-client'
import { useAppContext } from '../__root'

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

async function applyEvent(
  event: Record<string, unknown>,
  setThinkingSteps: Dispatch<SetStateAction<ThinkingStep[]>>,
  setMessages: Dispatch<SetStateAction<Message[]>>,
  setIsStreaming: Dispatch<SetStateAction<boolean>>,
  setStreamError: Dispatch<SetStateAction<string | null>>,
  setBackendOffline: (v: boolean) => void,
  onTicketCreated?: () => void,
): Promise<void> {
  const stage = event.stage as string

  if (stage === 'thinking') {
    setThinkingSteps([{ type: 'thinking' }])
  } else if (stage === 'intent') {
    setThinkingSteps([{ type: 'intent', label: event.label as string }])
  } else if (stage === 'tools_selected') {
    const tools = event.tools as string[]
    const replan = Boolean(event.replan)
    setThinkingSteps((prev) => [...prev, { type: 'tools_selected', tools, replan }])
  } else if (stage === 'tool_done') {
    if (event.tool === 'create_support_ticket' && Boolean(event.ok)) {
      onTicketCreated?.()
    }
    setThinkingSteps((prev) => [
      ...prev,
      { type: 'tool_done', tool: event.tool as string, ok: Boolean(event.ok) },
    ])
  } else if (stage === 'reasoning') {
    setThinkingSteps((prev) => [...prev, { type: 'reasoning' }])
  } else if (stage === 'done') {
    const assistantMsg: Message = {
      id: `msg-${Date.now()}`,
      role: 'assistant',
      content: (event.response as string) ?? 'Sorry, I could not process that request.',
      timestamp: new Date().toISOString(),
      tool_calls_made: (event.tool_calls_made as string[]) ?? [],
      evidence: (event.evidence as Record<string, unknown> | null) ?? null,
    }
    setMessages((prev) => [...prev, assistantMsg])
    setThinkingSteps([])
    setIsStreaming(false)
  } else if (stage === 'error') {
    setStreamError((event.message as string) ?? 'An error occurred.')
    setThinkingSteps([])
    setIsStreaming(false)
    setBackendOffline(true)
  }
}

export function AppChatPage() {
  const { setBackendOffline } = useAppContext()
  const queryClient = useQueryClient()
  const { sessionId } = useParams({ strict: false }) as { sessionId?: string }
  const [input, setInput] = useState('')
  const [messages, setMessages] = useState<Message[]>([
    {
      id: 'welcome',
      role: 'assistant',
      content:
        'Good day. This is EVA from the executive support desk. I am here to assist you personally with any billing, account, ticket, or policy related inquiries. How may I help you today?',
      timestamp: new Date().toISOString(),
    },
  ])
  const [thinkingSteps, setThinkingSteps] = useState<ThinkingStep[]>([])
  const [isStreaming, setIsStreaming] = useState(false)
  const [streamError, setStreamError] = useState<string | null>(null)
  const [initialLoading, setInitialLoading] = useState(!!sessionId)
  const [sessionError, setSessionError] = useState<string | null>(null)

  const ticketCreatedRef = useRef(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)
  const abortRef = useRef<AbortController | null>(null)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, thinkingSteps, isStreaming])

  useEffect(() => {
    if (inputRef.current) {
      inputRef.current.style.height = 'auto'
      inputRef.current.style.height = Math.min(inputRef.current.scrollHeight, 150) + 'px'
    }
  }, [input])

  useEffect(() => {
    if (!sessionId) {
      setInitialLoading(false)
      return
    }

    setMessages([{
      id: 'welcome',
      role: 'assistant',
      content:
        'Good day. This is EVA from the executive support desk. I am here to assist you personally with any billing, account, ticket, or policy related inquiries. How may I help you today?',
      timestamp: new Date().toISOString(),
    }])
    setInitialLoading(true)
    setSessionError(null)

    api.getSessionMessages(sessionId).then((res) => {
      setInitialLoading(false)
      if (!res.success) {
        setSessionError(res.error ?? 'Session not found')
        return
      }
      if (res.data?.messages && res.data.messages.length > 0) {
        const loadedMessages: Message[] = res.data.messages.map((m) => ({
          id: m.id,
          role: m.role as 'user' | 'assistant',
          content: m.content,
          timestamp: m.created_at,
          tool_calls_made: [],
          evidence: null,
        }))
        setMessages(loadedMessages)
      }
    }).catch((err) => {
      setInitialLoading(false)
      if (err && typeof err === 'object' && 'status' in err && err.status === 404) {
        setSessionError('Session not found')
      }
    })
  }, [sessionId])

  const handleSubmit = useCallback(async () => {
    const trimmed = input.trim()
    if (!trimmed || isStreaming) return

    const userMsg: Message = {
      id: `msg-${Date.now()}`,
      role: 'user',
      content: trimmed,
      timestamp: new Date().toISOString(),
    }
    setMessages((prev) => [...prev, userMsg])
    setInput('')
    setThinkingSteps([])
    setStreamError(null)
    setSessionError(null)
    setIsStreaming(true)
    ticketCreatedRef.current = false

    const abort = new AbortController()
    abortRef.current = abort

    const token =
      typeof localStorage !== 'undefined' ? localStorage.getItem('jwt') : null

    try {
      const res = await fetch(`${API_BASE}/api/v1/chat/stream`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({
          message: trimmed,
          customer_id: mock.customerId,
          ...(sessionId ? { session_id: sessionId } : {}),
        }),
        signal: abort.signal,
      })

      if (!res.ok || !res.body) {
        throw new Error(`HTTP ${res.status}`)
      }

      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { value, done } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })

        const lines = buffer.split('\n')
        buffer = lines.pop() ?? ''

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          const raw = line.slice(6).trim()
          if (!raw) continue

          let event: Record<string, unknown>
          try {
            event = JSON.parse(raw)
          } catch {
            continue
          }

          await applyEvent(
            event, setThinkingSteps, setMessages, setIsStreaming, setStreamError, setBackendOffline,
            () => { ticketCreatedRef.current = true },
          )
          await new Promise<void>((r) => setTimeout(r, 0))
        }
      }
      if (ticketCreatedRef.current) {
        queryClient.invalidateQueries({ queryKey: ['ticketList'] })
      }
      queryClient.invalidateQueries({ queryKey: ['sessions'] })
    } catch (err) {
      if ((err as Error).name === 'AbortError') return
      setStreamError('Connection lost. The backend may be unreachable.')
      setThinkingSteps([])
      setIsStreaming(false)
      setBackendOffline(true)

      const fallback: Message = {
        id: `msg-${Date.now()}`,
        role: 'assistant',
        content: 'Sorry, I could not process that request. The backend appears to be unreachable.',
        timestamp: new Date().toISOString(),
      }
      setMessages((prev) => [...prev, fallback])
    }
  }, [input, isStreaming, sessionId, setBackendOffline, queryClient])

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      void handleSubmit()
    }
  }

  return (
    <div className="flex flex-col h-full sm:p-6 p-4">
      {/* Header */}
      <div className="flex items-center gap-3 mb-4">
        <div className="p-2 rounded-sm bg-surface-stone dark:bg-surface-dark-elevated">
          <Sparkles size={20} className="text-brand-coral" />
        </div>
        <div>
          <h1 className="font-display text-heading-feature text-ink dark:text-white">AI Chat</h1>
          <p className="text-caption text-muted-slate">
            Ask questions about your account, billing, or support
          </p>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto scrollbar-thin space-y-4 pr-3 sm:pr-2 mb-4">
        {initialLoading ? (
          <div className="flex justify-center items-center py-12">
            <div className="animate-pulse text-muted-slate">Loading messages...</div>
          </div>
        ) : (
          messages.map((msg) => (
            <ChatMessage key={msg.id} message={msg} />
          ))
        )}

        {/* Live thinking panel */}
        {isStreaming && (
          <ThinkingPanel steps={thinkingSteps} isStreaming={isStreaming} />
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Error banner */}
      {sessionError && (
        <div className="mb-3 px-4 py-3 rounded-lg chip-red flex items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <AlertCircle size={16} />
            <span>{sessionError}</span>
          </div>
          <Link to="/app/chat" className="text-xs font-medium underline hover:no-underline whitespace-nowrap">
            New conversation
          </Link>
        </div>
      )}
      {!sessionError && streamError && (
        <div className="mb-3 px-4 py-2 rounded-lg chip-red flex items-center gap-2">
          <AlertCircle size={16} />
          {streamError}
        </div>
      )}

      {/* Input */}
      <div className="flex gap-3 items-end">
        <div className="flex-1 relative">
          <textarea
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Type your message... (Shift+Enter for new line)"
            rows={1}
            className="input resize-none pr-12 py-3 min-h-[48px] max-h-[150px]"
            disabled={isStreaming}
          />
        </div>
        <button
          onClick={() => void handleSubmit()}
          disabled={!input.trim() || isStreaming}
          className="btn-pill-primary h-[48px] w-[48px] p-0 flex-shrink-0"
          aria-label="Send message"
        >
          <Send size={18} />
        </button>
      </div>

      <p className="text-micro text-muted-slate mt-2 text-center">
        Responses are AI-generated and may not always be accurate.
      </p>
    </div>
  )
}

import { useState, useRef, useEffect } from 'react'
import { Send, Sparkles, AlertCircle } from 'lucide-react'
import { useMutation } from '@tanstack/react-query'
import ChatMessage, { type Message } from '../components/ChatMessage'
import { api, mock } from '../lib/api-client'
import { useAppContext } from './__root'

export function ChatPage() {
  const { setBackendOffline } = useAppContext()
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
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)

  const chatMutation = useMutation({
    mutationFn: (message: string) =>
      api.chat({ message, customer_id: mock.customerId }),
    onSuccess: (result: Record<string, unknown>) => {
      if (result && !result.response) {
        setBackendOffline(true)
        const fallback: Message = {
          id: `msg-${Date.now()}`,
          role: 'assistant',
          content: 'Sorry, I could not process that request. The backend appears to be unreachable.',
          timestamp: new Date().toISOString(),
        }
        setMessages((prev) => [...prev, fallback])
        return
      }
      const assistantMsg: Message = {
        id: `msg-${Date.now()}`,
        role: 'assistant',
        content: (result.response as string) ?? 'Sorry, I could not process that request.',
        timestamp: new Date().toISOString(),
        tool_calls_made: (result.tool_calls_made as string[]) ?? [],
        evidence: (result.evidence as Record<string, unknown> | null) ?? null,
      }
      setMessages((prev) => [...prev, assistantMsg])
    },
    onError: () => {
      setBackendOffline(true)
      const fallback: Message = {
        id: `msg-${Date.now()}`,
        role: 'assistant',
        content: 'Sorry, I could not process that request. The backend returned an error.',
        timestamp: new Date().toISOString(),
      }
      setMessages((prev) => [...prev, fallback])
    },
  })

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  // Auto-resize textarea
  useEffect(() => {
    if (inputRef.current) {
      inputRef.current.style.height = 'auto'
      inputRef.current.style.height = Math.min(inputRef.current.scrollHeight, 150) + 'px'
    }
  }, [input])

  const handleSubmit = () => {
    const trimmed = input.trim()
    if (!trimmed || chatMutation.isPending) return

    const userMsg: Message = {
      id: `msg-${Date.now()}`,
      role: 'user',
      content: trimmed,
      timestamp: new Date().toISOString(),
    }
    setMessages((prev) => [...prev, userMsg])
    setInput('')
    chatMutation.mutate(trimmed)
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit()
    }
  }

  return (
    <div className="flex flex-col h-[calc(100vh-7rem)] animate-fade-in">
      {/* Header */}
      <div className="flex items-center gap-3 mb-4">
        <div className="p-2 rounded-lg bg-brand-50 dark:bg-brand-950/30">
          <Sparkles size={20} className="text-brand-600 dark:text-brand-400" />
        </div>
        <div>
          <h1 className="text-lg font-bold text-gray-900 dark:text-gray-100">AI Chat</h1>
          <p className="text-xs text-gray-500 dark:text-gray-400">
            Ask questions about your account, billing, or support
          </p>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto scrollbar-thin space-y-4 pr-2 mb-4">
        {messages.map((msg) => (
          <ChatMessage key={msg.id} message={msg} />
        ))}
        {chatMutation.isPending && (
          <div className="flex items-center gap-2 text-sm text-gray-400 dark:text-gray-500 animate-pulse">
            <div className="w-2 h-2 rounded-full bg-brand-500 animate-bounce" style={{ animationDelay: '0ms' }} />
            <div className="w-2 h-2 rounded-full bg-brand-500 animate-bounce" style={{ animationDelay: '150ms' }} />
            <div className="w-2 h-2 rounded-full bg-brand-500 animate-bounce" style={{ animationDelay: '300ms' }} />
            <span className="ml-1">Assistant is thinking...</span>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Error banner */}
      {chatMutation.isError && (
        <div className="mb-3 px-4 py-2 rounded-lg bg-red-50 dark:bg-red-950/30 border border-red-200 dark:border-red-800 text-sm text-red-600 dark:text-red-400 flex items-center gap-2">
          <AlertCircle size={16} />
          Failed to send message. Showing sample response instead.
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
            disabled={chatMutation.isPending}
          />
        </div>
        <button
          onClick={handleSubmit}
          disabled={!input.trim() || chatMutation.isPending}
          className="btn-primary h-[48px] w-[48px] p-0 flex-shrink-0"
          aria-label="Send message"
        >
          <Send size={18} />
        </button>
      </div>

      <p className="text-[10px] text-gray-400 dark:text-gray-500 mt-2 text-center">
        Responses are AI-generated and may not always be accurate.
      </p>
    </div>
  )
}

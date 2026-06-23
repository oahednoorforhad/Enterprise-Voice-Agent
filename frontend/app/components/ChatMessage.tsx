import { Bot, User, Copy, Check } from 'lucide-react'
import { useState } from 'react'

export interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: string
  tool_calls_made?: string[]
  evidence?: Record<string, unknown> | null
}

interface ChatMessageProps {
  message: Message
}

export default function ChatMessage({ message }: ChatMessageProps) {
  const [copied, setCopied] = useState(false)
  const isUser = message.role === 'user'

  const handleCopy = () => {
    navigator.clipboard.writeText(message.content)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div
      className={`flex gap-3 ${isUser ? 'flex-row-reverse' : ''} animate-fade-in`}
    >
      {/* Avatar */}
      <div
        className={`flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center ${
          isUser
            ? 'bg-brand-near text-white dark:bg-white dark:text-ink'
            : 'bg-surface-stone text-muted-slate dark:bg-surface-dark-elevated dark:text-gray-300'
        }`}
      >
        {isUser ? <User size={16} /> : <Bot size={16} />}
      </div>

      {/* Bubble */}
      <div className={`flex flex-col max-w-[80%] ${isUser ? 'items-end' : 'items-start'}`}>
        <div
          className={`px-4 py-3 text-body-small leading-relaxed ${
            isUser
              ? 'bg-brand-near text-white dark:bg-white dark:text-ink rounded-lg rounded-tr-sm'
              : 'bg-surface-stone text-ink dark:bg-surface-dark-elevated dark:text-gray-100 rounded-lg rounded-tl-sm'
          }`}
        >
          <p className="whitespace-pre-wrap">{message.content}</p>
        </div>

        {/* Metadata row */}
        <div className={`flex items-center gap-2 mt-1.5 ${isUser ? 'flex-row-reverse' : ''}`}>
          <span className="text-micro text-muted-slate">
            {new Date(message.timestamp).toLocaleTimeString([], {
              hour: '2-digit',
              minute: '2-digit',
            })}
          </span>

          {/* Tool calls */}
          {!isUser && message.tool_calls_made && message.tool_calls_made.length > 0 && (
            <span className="chip-coral text-[11px] py-0.5 px-2">
              {message.tool_calls_made.length} tool{message.tool_calls_made.length > 1 ? 's' : ''}
            </span>
          )}

          {/* Copy */}
          <button
            onClick={handleCopy}
            className="text-muted-slate hover:text-ink dark:hover:text-gray-300 transition-colors"
            title="Copy message"
          >
            {copied ? <Check size={12} /> : <Copy size={12} />}
          </button>
        </div>
      </div>
    </div>
  )
}

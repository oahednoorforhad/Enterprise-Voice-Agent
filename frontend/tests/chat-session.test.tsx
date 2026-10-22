/**
 * Unit tests for the session-aware AppChatPage component.
 *
 * Mocks @tanstack/react-router (Link, useParams),
 * @tanstack/react-query (useQueryClient),
 * the API client, child components (ChatMessage, ThinkingPanel),
 * and __root (useAppContext).
 *
 * Tests: loading messages on mount, welcome message for new sessions,
 * error states, and sending session_id in stream requests.
 */

import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import React from 'react'

// jsdom does not implement scrollIntoView — stub it
if (typeof Element !== 'undefined' && !Element.prototype.scrollIntoView) {
  Element.prototype.scrollIntoView = vi.fn()
}

// ---- Mutable control variables (set per-test before render) -----------------
// These are used inside vi.mock factories via closure. vi.mock is hoisted but
// factories run lazily — by then these variables are already defined.

let mockParams: Record<string, string | undefined> = {}
let mockSessionMessagesResult: unknown = {
  success: true,
  data: { session_id: '', title: null, messages: [] },
}
let mockCustomerId = 'c63d2f89-9aa3-4157-8205-a7d6cfc23207'

// ---- Hoisted mock functions (guaranteed available before vi.mock factories) -

const { mockGetSessionMessages, mockSetBackendOffline } = vi.hoisted(() => ({
  mockGetSessionMessages: vi.fn(),
  mockSetBackendOffline: vi.fn(),
}))

// ---- Mock @tanstack/react-router -------------------------------------------

vi.mock('@tanstack/react-router', () => ({
  Link: ({ children, to, ...props }: { children: React.ReactNode; to: string; [key: string]: unknown }) =>
    React.createElement('a', { href: to, ...props }, children),
  useParams: () => mockParams,
  useLocation: () => ({ pathname: '/app/chat' }),
  createRootRoute: (opts: { component: React.ComponentType }) => opts,
  Outlet: () => null,
}))

// ---- Mock @tanstack/react-query ---------------------------------------------

vi.mock('@tanstack/react-query', () => ({
  useQueryClient: () => ({
    invalidateQueries: vi.fn(),
  }),
  QueryClient: function MockQueryClient() {
    this.invalidateQueries = vi.fn()
  } as unknown as new (...args: unknown[]) => { invalidateQueries: ReturnType<typeof vi.fn> },
  QueryClientProvider: ({ children }: { children: React.ReactNode }) => children,
}))

// ---- Mock api client --------------------------------------------------------

vi.mock('../app/lib/api-client', () => ({
  API_BASE: 'http://localhost:8000',
  authFetch: (input: string, init?: RequestInit) => fetch(input, init),
  api: {
    getSessionMessages: (...args: unknown[]) => mockGetSessionMessages(...args),
  },
  mock: {
    get customerId() {
      return mockCustomerId
    },
  },
}))

// ---- Mock child components --------------------------------------------------

vi.mock('../../components/ChatMessage', () => ({
  default: ({ message }: { message: { role: string; content: string } }) =>
    React.createElement(
      'div',
      { 'data-testid': `msg-${message.role}` },
      message.content,
    ),
}))

vi.mock('../../components/ThinkingPanel', () => ({
  default: () => React.createElement('div', { 'data-testid': 'thinking-panel' }),
}))

// ---- Mock __root context ----------------------------------------------------

vi.mock('../__root', () => ({
  useAppContext: () => ({
    backendOffline: false,
    setBackendOffline: mockSetBackendOffline,
    isDark: false,
    onToggleDark: vi.fn(),
  }),
}))

// ---- Import after mocks -----------------------------------------------------

import { AppChatPage } from '../app/routes/app/chat'

// ---- Helpers ----------------------------------------------------------------

/** Creates a mock ReadableStream that yields the given chunks. */
function mockResponseStream(chunks: string[]): Response {
  const encoder = new TextEncoder()
  return {
    ok: true,
    status: 200,
    body: new ReadableStream({
      start(controller) {
        for (const chunk of chunks) {
          controller.enqueue(encoder.encode(chunk))
        }
        controller.close()
      },
    }),
  } as unknown as Response
}

const defaultWelcomeText =
  'Good day. This is EVA from the executive support desk.'

function renderChat() {
  return render(React.createElement(AppChatPage))
}

// ---- Tests ------------------------------------------------------------------

describe('AppChatPage session awareness', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockParams = {}
    mockSessionMessagesResult = { success: true, data: { session_id: '', title: null, messages: [] } }
    mockCustomerId = 'c63d2f89-9aa3-4157-8205-a7d6cfc23207'
    mockGetSessionMessages.mockImplementation(() => Promise.resolve(mockSessionMessagesResult))
    globalThis.fetch = vi.fn()
  })

  // ---- No session ID ---------------------------------------------------------

  it('shows welcome message for new (empty) session', () => {
    mockParams = {}
    renderChat()

    expect(screen.getByText(defaultWelcomeText, { exact: false })).toBeTruthy()
    // Should NOT have called getSessionMessages
    expect(mockGetSessionMessages).not.toHaveBeenCalled()
  })

  it('does not show loading indicator when no sessionId', () => {
    mockParams = {}
    renderChat()

    expect(screen.queryByText('Loading messages...')).toBeNull()
  })

  // ---- Loading state ---------------------------------------------------------

  it('shows loading indicator while fetching session messages', () => {
    mockParams = { sessionId: 'sess-001' }
    // Return a promise that never resolves during this test
    mockGetSessionMessages.mockReturnValue(new Promise(() => {}))
    renderChat()

    expect(screen.getByText('Loading messages...')).toBeTruthy()
    expect(mockGetSessionMessages).toHaveBeenCalledWith('sess-001')
  })

  // ---- Loads messages --------------------------------------------------------

  it('loads messages from backend on mount with session_id', async () => {
    mockParams = { sessionId: 'sess-001' }
    mockSessionMessagesResult = {
      success: true,
      data: {
        session_id: 'sess-001',
        title: 'Previous chat',
        messages: [
          { id: 'm1', role: 'user', content: 'Hello from before', created_at: '2026-06-26T10:00:00Z', tool_calls: null },
          { id: 'm2', role: 'assistant', content: 'Hi, how can I help?', created_at: '2026-06-26T10:00:05Z', tool_calls: null },
        ],
      },
    }
    mockGetSessionMessages.mockResolvedValue(mockSessionMessagesResult)

    renderChat()

    // Wait for the messages to render (welcome message replaced)
    await waitFor(() => {
      expect(screen.getByText('Hello from before')).toBeTruthy()
    })
    expect(screen.getByText('Hi, how can I help?')).toBeTruthy()
    // Welcome message should NOT be shown
    expect(screen.queryByText(defaultWelcomeText, { exact: false })).toBeNull()
    expect(mockGetSessionMessages).toHaveBeenCalledWith('sess-001')
  })

  it('keeps welcome message for empty session (no messages returned)', async () => {
    mockParams = { sessionId: 'sess-empty' }
    mockSessionMessagesResult = {
      success: true,
      data: { session_id: 'sess-empty', title: null, messages: [] },
    }
    mockGetSessionMessages.mockResolvedValue(mockSessionMessagesResult)

    renderChat()

    // Wait for loading to finish — welcome message should remain
    await waitFor(() => {
      expect(screen.queryByText('Loading messages...')).toBeNull()
    })
    expect(screen.getByText(defaultWelcomeText, { exact: false })).toBeTruthy()
  })

  // ---- Session switching -----------------------------------------------------

  it('clears messages and shows loading when switching sessions', async () => {
    // Start with session A that has messages
    mockParams = { sessionId: 'sess-A' }
    mockSessionMessagesResult = {
      success: true,
      data: {
        session_id: 'sess-A',
        title: 'Session A',
        messages: [
          { id: 'a1', role: 'user', content: 'Hello from A', created_at: '2026-06-26T10:00:00Z', tool_calls: null },
        ],
      },
    }
    mockGetSessionMessages.mockResolvedValue(mockSessionMessagesResult)

    const { rerender } = renderChat()

    // Wait for messages from session A to appear
    await waitFor(() => {
      expect(screen.getByText('Hello from A')).toBeTruthy()
    })
    expect(screen.queryByText('Loading messages...')).toBeNull()

    // Prepare mock for session B — keep promise unresolved so we can verify loading state
    let resolveSessionB!: (value: unknown) => void
    mockGetSessionMessages.mockReturnValue(
      new Promise((resolve) => { resolveSessionB = resolve }),
    )

    // Switch to session B
    mockParams = { sessionId: 'sess-B' }
    rerender(React.createElement(AppChatPage))

    // INSTANTLY: old messages cleared, loading indicator shown
    await waitFor(() => {
      expect(screen.queryByText('Hello from A')).toBeNull()
    })
    expect(screen.getByText('Loading messages...')).toBeTruthy()
    expect(mockGetSessionMessages).toHaveBeenCalledWith('sess-B')

    // Resolve with empty messages → welcome message should appear
    resolveSessionB({
      success: true,
      data: { session_id: 'sess-B', title: null, messages: [] },
    })

    await waitFor(() => {
      expect(screen.queryByText('Loading messages...')).toBeNull()
    })
    expect(screen.getByText(defaultWelcomeText, { exact: false })).toBeTruthy()
  })

  // ---- Error state -----------------------------------------------------------

  it('shows error banner when session fetch fails', async () => {
    mockParams = { sessionId: 'sess-bad' }
    mockSessionMessagesResult = {
      success: false,
      data: null,
      error: 'Session not found',
    }
    mockGetSessionMessages.mockResolvedValue(mockSessionMessagesResult)

    renderChat()

    await waitFor(() => {
      expect(screen.getByText('Session not found')).toBeTruthy()
    })
    // Should show a "New conversation" link
    expect(screen.getByText('New conversation')).toBeTruthy()
  })

  it('shows error banner on 404 network response', async () => {
    mockParams = { sessionId: 'sess-404' }
    // Simulate a rejected promise like a 404 error
    mockGetSessionMessages.mockRejectedValue({ status: 404 })

    renderChat()

    await waitFor(() => {
      expect(screen.getByText('Session not found')).toBeTruthy()
    })
  })

  // ---- Stream request body ---------------------------------------------------

  it('sends session_id in stream request body', async () => {
    mockParams = { sessionId: 'sess-stream' }
    mockSessionMessagesResult = {
      success: true,
      data: { session_id: 'sess-stream', title: null, messages: [] },
    }
    mockGetSessionMessages.mockResolvedValue(mockSessionMessagesResult)

    // Mock fetch to capture the request body
    let capturedBody: string | null = null
    globalThis.fetch = vi.fn().mockImplementation(async (_url: string, opts: RequestInit) => {
      capturedBody = opts.body as string
      return mockResponseStream([
        'data: {"stage":"done","response":"Hello from EVA"}\n',
      ])
    })

    renderChat()

    // Wait for loading to finish
    await waitFor(() => {
      expect(screen.queryByText('Loading messages...')).toBeNull()
    })

    // Type a message and submit
    const textarea = screen.getByPlaceholderText(/Type your message/)
    expect(textarea).toBeTruthy()

    fireEvent.change(textarea, { target: { value: 'Check my bill' } })
    const sendBtn = screen.getByLabelText('Send message')
    fireEvent.click(sendBtn)

    // Wait for fetch to be called
    await waitFor(() => {
      expect(capturedBody).not.toBeNull()
    })

    const parsed = JSON.parse(capturedBody!)
    expect(parsed.message).toBe('Check my bill')
    expect(parsed.session_id).toBe('sess-stream')
    expect(parsed.customer_id).toBe(mockCustomerId)
  })

  it('does not send session_id when no session is active', async () => {
    mockParams = {}
    mockGetSessionMessages.mockResolvedValue({
      success: true,
      data: { session_id: '', title: null, messages: [] },
    })

    let capturedBody: string | null = null
    globalThis.fetch = vi.fn().mockImplementation(async (_url: string, opts: RequestInit) => {
      capturedBody = opts.body as string
      return mockResponseStream([
        'data: {"stage":"done","response":"OK"}\n',
      ])
    })

    renderChat()

    const textarea = screen.getByPlaceholderText(/Type your message/)
    fireEvent.change(textarea, { target: { value: 'Hello' } })
    const sendBtn = screen.getByLabelText('Send message')
    fireEvent.click(sendBtn)

    await waitFor(() => {
      expect(capturedBody).not.toBeNull()
    })

    const parsed = JSON.parse(capturedBody!)
    expect(parsed.session_id).toBeUndefined()
    expect(parsed.message).toBe('Hello')
  })
})

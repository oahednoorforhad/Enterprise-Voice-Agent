/**
 * Unit tests for session-related API client methods.
 *
 * Mocks fetch globally to avoid real network dependencies.
 * Covers listSessions, getSessionMessages, and createSession.
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { api } from '../app/lib/api-client'
import type { ToolResult, SessionListResponse, SessionMessagesResponse, CreateSessionResponse } from '../app/lib/api-client'

// ---- Helpers ---------------------------------------------------------------

function mockFetchResponse<T>(data: ToolResult<T>, ok = true): void {
  globalThis.fetch = vi.fn().mockResolvedValue({
    ok,
    status: ok ? 200 : 404,
    statusText: ok ? 'OK' : 'Not Found',
    json: () => Promise.resolve(data),
  } as Response)
}

function mockFetchNetworkError(): void {
  globalThis.fetch = vi.fn().mockRejectedValue(new TypeError('Failed to fetch'))
}

// ---- listSessions ----------------------------------------------------------

describe('api.listSessions', () => {
  const sessionsData: SessionListResponse = {
    sessions: [
      {
        session_id: 'sess-001',
        title: 'Billing inquiry',
        started_at: '2026-06-26T10:00:00Z',
        ended_at: null,
        message_count: 5,
        last_message_preview: 'Can you check my invoice?',
      },
      {
        session_id: 'sess-002',
        title: 'Support request',
        started_at: '2026-06-25T14:30:00Z',
        ended_at: '2026-06-25T15:00:00Z',
        message_count: 12,
        last_message_preview: 'Thanks for the help!',
      },
    ],
    total: 2,
  }

  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('returns session list on success', async () => {
    mockFetchResponse<ToolResult<SessionListResponse>>({
      success: true,
      data: sessionsData,
      error: null,
    })

    const result = await api.listSessions()
    expect(result.success).toBe(true)
    expect(result.data).toEqual(sessionsData)
    expect(result.error).toBeNull()
  })

  it('parses session items correctly', async () => {
    mockFetchResponse<ToolResult<SessionListResponse>>({
      success: true,
      data: sessionsData,
      error: null,
    })

    const result = await api.listSessions()
    expect(result.data?.sessions).toHaveLength(2)
    expect(result.data?.sessions[0].session_id).toBe('sess-001')
    expect(result.data?.sessions[0].title).toBe('Billing inquiry')
    expect(result.data?.sessions[1].last_message_preview).toBe('Thanks for the help!')
  })

  it('returns empty sessions list', async () => {
    mockFetchResponse<ToolResult<SessionListResponse>>({
      success: true,
      data: { sessions: [], total: 0 },
      error: null,
    })

    const result = await api.listSessions()
    expect(result.success).toBe(true)
    expect(result.data?.sessions).toHaveLength(0)
    expect(result.data?.total).toBe(0)
  })

  it('handles network error gracefully', async () => {
    mockFetchNetworkError()

    const result = await api.listSessions()
    expect(result.success).toBe(false)
    expect(result.data).toBeNull()
    expect(result.error).toContain('Failed to fetch')
  })
})

// ---- getSessionMessages ----------------------------------------------------

describe('api.getSessionMessages', () => {
  const messagesData: SessionMessagesResponse = {
    session_id: 'sess-001',
    title: 'Billing inquiry',
    messages: [
      {
        id: 'msg-001',
        role: 'user',
        content: 'Can you check my invoice?',
        created_at: '2026-06-26T10:00:00Z',
        tool_calls: null,
      },
      {
        id: 'msg-002',
        role: 'assistant',
        content: 'Sure, let me look that up.',
        created_at: '2026-06-26T10:00:05Z',
        tool_calls: { tools: ['get_billing_history'] },
      },
    ],
  }

  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('returns messages for a valid session', async () => {
    mockFetchResponse<ToolResult<SessionMessagesResponse>>({
      success: true,
      data: messagesData,
      error: null,
    })

    const result = await api.getSessionMessages('sess-001')
    expect(result.success).toBe(true)
    expect(result.data?.session_id).toBe('sess-001')
    expect(result.data?.messages).toHaveLength(2)
    expect(result.data?.messages[0].content).toBe('Can you check my invoice?')
  })

  it('calls the correct URL with session ID', async () => {
    const fetchSpy = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve({ success: true, data: messagesData, error: null }),
    } as Response)
    globalThis.fetch = fetchSpy

    await api.getSessionMessages('sess-001')
    const callUrl = fetchSpy.mock.calls[0][0] as string
    expect(callUrl).toContain('/api/v1/chat/sessions/sess-001/messages')
  })

  it('returns empty messages array for a new session', async () => {
    mockFetchResponse<ToolResult<SessionMessagesResponse>>({
      success: true,
      data: { session_id: 'sess-empty', title: null, messages: [] },
      error: null,
    })

    const result = await api.getSessionMessages('sess-empty')
    expect(result.success).toBe(true)
    expect(result.data?.messages).toHaveLength(0)
  })

  it('returns error for invalid session ID', async () => {
    // The backend always returns HTTP 200 with success:false for business errors
    mockFetchResponse<ToolResult<SessionMessagesResponse>>({
      success: false,
      data: null,
      error: 'Session not found',
    })

    const result = await api.getSessionMessages('invalid-id')
    expect(result.success).toBe(false)
    expect(result.data).toBeNull()
    expect(result.error).toBe('Session not found')
  })

  it('handles network error', async () => {
    mockFetchNetworkError()

    const result = await api.getSessionMessages('sess-001')
    expect(result.success).toBe(false)
    expect(result.data).toBeNull()
    expect(result.error).toContain('Failed to fetch')
  })
})

// ---- createSession ---------------------------------------------------------

describe('api.createSession', () => {
  const newSessionData: CreateSessionResponse = {
    session_id: 'sess-new-001',
    title: null,
    started_at: '2026-06-27T12:00:00Z',
  }

  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('returns new session data on success', async () => {
    mockFetchResponse<ToolResult<CreateSessionResponse>>({
      success: true,
      data: newSessionData,
      error: null,
    })

    const result = await api.createSession()
    expect(result.success).toBe(true)
    expect(result.data?.session_id).toBe('sess-new-001')
    expect(result.data?.title).toBeNull()
  })

  it('calls POST /api/v1/chat/sessions', async () => {
    const fetchSpy = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve({ success: true, data: newSessionData, error: null }),
    } as Response)
    globalThis.fetch = fetchSpy

    await api.createSession()
    const callUrl = fetchSpy.mock.calls[0][0] as string
    const callMethod = fetchSpy.mock.calls[0][1]?.method ?? 'unknown'
    expect(callUrl).toContain('/api/v1/chat/sessions')
    expect(callMethod).toBe('POST')
  })

  it('handles network error', async () => {
    mockFetchNetworkError()

    const result = await api.createSession()
    expect(result.success).toBe(false)
    expect(result.data).toBeNull()
    expect(result.error).toContain('Failed to fetch')
  })
})

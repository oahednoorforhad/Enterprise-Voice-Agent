/**
 * Tests for frontend/app/hooks/useVoiceSession.ts
 *
 * No real WebSocket or AudioContext is created — all network is mocked.
 * Tests focus on the state machine transitions driven by server events.
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { installMockWebSocket, restoreMockWebSocket } from './__mocks__/websocket'
import { useVoiceSession } from '../app/hooks/useVoiceSession'

// Stub AudioContext and AudioWorklet so they don't require a real browser
vi.mock('../app/lib/audio-worklet', () => ({
  createResampler: vi.fn().mockResolvedValue({ stop: vi.fn() }),
  decodePCMFromBase64: vi.fn().mockReturnValue(new Float32Array(0)),
  encodePCMToBase64: vi.fn().mockReturnValue(''),
  schedulePlayback: vi.fn(),
}))

// Stub global AudioContext
globalThis.AudioContext = vi.fn().mockImplementation(() => ({
  state: 'running',
  close: vi.fn().mockResolvedValue(undefined),
  createBufferSource: vi.fn().mockReturnValue({
    buffer: null,
    connect: vi.fn(),
    start: vi.fn(),
  }),
  createBuffer: vi.fn(),
  destination: {},
})) as unknown as typeof AudioContext

const CUSTOMER_ID = 'c63d2f89-9aa3-4157-8205-a7d6cfc23207'

describe('useVoiceSession state machine', () => {
  let wsControl: ReturnType<typeof installMockWebSocket>

  beforeEach(() => {
    wsControl = installMockWebSocket()
  })

  afterEach(() => {
    restoreMockWebSocket()
    vi.clearAllMocks()
  })

  it('starts in idle state', () => {
    const { result } = renderHook(() => useVoiceSession())
    expect(result.current.state).toBe('idle')
    expect(result.current.sessionId).toBeNull()
    expect(result.current.transcript).toEqual([])
    expect(result.current.activeTools).toEqual([])
    expect(result.current.error).toBeNull()
  })

  it('transitions to connecting then active on session_started', async () => {
    const { result } = renderHook(() => useVoiceSession())

    await act(async () => {
      await result.current.startSession(CUSTOMER_ID)
    })

    expect(result.current.state).toBe('connecting')

    // Simulate server: session_started
    await act(async () => {
      const ws = wsControl.getInstance()!
      ws.simulateMessage(
        JSON.stringify({ type: 'session_started', session_id: 'sess-abc' })
      )
    })

    expect(result.current.state).toBe('active')
    expect(result.current.sessionId).toBe('sess-abc')
  })

  it('appends transcript lines on transcript events', async () => {
    const { result } = renderHook(() => useVoiceSession())

    await act(async () => {
      await result.current.startSession(CUSTOMER_ID)
      const ws = wsControl.getInstance()!
      ws.simulateMessage(JSON.stringify({ type: 'session_started', session_id: 'sess-t' }))
      ws.simulateMessage(JSON.stringify({ type: 'transcript', role: 'user', text: 'Hello' }))
      ws.simulateMessage(JSON.stringify({ type: 'transcript', role: 'assistant', text: 'Hi there' }))
    })

    expect(result.current.transcript).toEqual([
      { role: 'user', text: 'Hello' },
      { role: 'assistant', text: 'Hi there' },
    ])
  })

  it('tracks active tools on tool_call events', async () => {
    const { result } = renderHook(() => useVoiceSession())

    await act(async () => {
      await result.current.startSession(CUSTOMER_ID)
      const ws = wsControl.getInstance()!
      ws.simulateMessage(JSON.stringify({ type: 'session_started', session_id: 's' }))
      ws.simulateMessage(JSON.stringify({ type: 'tool_call', tool_name: 'get_billing_history', status: 'calling' }))
    })

    expect(result.current.activeTools).toContain('get_billing_history')

    await act(async () => {
      const ws = wsControl.getInstance()!
      ws.simulateMessage(JSON.stringify({ type: 'tool_call', tool_name: 'get_billing_history', status: 'done' }))
    })

    expect(result.current.activeTools).not.toContain('get_billing_history')
  })

  it('transitions to ended on session_ended event', async () => {
    const { result } = renderHook(() => useVoiceSession())

    await act(async () => {
      await result.current.startSession(CUSTOMER_ID)
      const ws = wsControl.getInstance()!
      ws.simulateMessage(JSON.stringify({ type: 'session_started', session_id: 's' }))
      ws.simulateMessage(JSON.stringify({ type: 'session_ended', session_id: 's' }))
    })

    expect(result.current.state).toBe('ended')
  })

  it('transitions to error on error event', async () => {
    const { result } = renderHook(() => useVoiceSession())

    await act(async () => {
      await result.current.startSession(CUSTOMER_ID)
      const ws = wsControl.getInstance()!
      ws.simulateMessage(JSON.stringify({ type: 'session_started', session_id: 's' }))
      ws.simulateMessage(JSON.stringify({ type: 'error', message: 'API limit exceeded' }))
    })

    expect(result.current.state).toBe('error')
    expect(result.current.error).toBe('API limit exceeded')
  })

  it('stopSession sends end_of_audio and transitions to ending', async () => {
    const { result } = renderHook(() => useVoiceSession())

    await act(async () => {
      await result.current.startSession(CUSTOMER_ID)
      const ws = wsControl.getInstance()!
      ws.simulateMessage(JSON.stringify({ type: 'session_started', session_id: 's' }))
    })

    await act(async () => {
      result.current.stopSession()
    })

    const ws = wsControl.getInstance()!
    const sentMessages = ws.sent
    expect(sentMessages.some((m) => m.includes('end_of_audio'))).toBe(true)
    expect(result.current.state).toBe('ending')
  })

  it('ignores malformed server messages without crashing', async () => {
    const { result } = renderHook(() => useVoiceSession())

    await act(async () => {
      await result.current.startSession(CUSTOMER_ID)
      const ws = wsControl.getInstance()!
      ws.simulateMessage('not valid json {{{{')
      ws.simulateMessage(JSON.stringify({ type: 'session_started', session_id: 'ok' }))
    })

    // Should still work after malformed message
    expect(result.current.state).toBe('active')
  })
})

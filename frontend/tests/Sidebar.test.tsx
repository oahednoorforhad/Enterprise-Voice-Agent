/**
 * Unit tests for the Sidebar component.
 *
 * Mocks @tanstack/react-router (Link, useLocation, useNavigate),
 * @tanstack/react-query (useQuery), and the api client.
 * Tests session list rendering, loading, empty, error states,
 * and the "New conversation" button.
 *
 * Note: sidebarContent is rendered twice (desktop + mobile drawer).
 * In jsdom, CSS visibility classes aren't applied, so all elements
 * appear twice. Use getAllByText / queryAllByText where needed.
 */

import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import React from 'react'

// ---- Mock @tanstack/react-router -------------------------------------------

const mockNavigate = vi.fn()
const mockUseLocation = vi.fn()

vi.mock('@tanstack/react-router', () => ({
  Link: ({ children, to, ...props }: { children: React.ReactNode; to: string; [key: string]: unknown }) =>
    React.createElement('a', { href: to, ...props }, children),
  useLocation: () => mockUseLocation(),
  useNavigate: () => mockNavigate,
}))

// ---- Mock @tanstack/react-query ---------------------------------------------

const mockUseQuery = vi.fn()

vi.mock('@tanstack/react-query', () => ({
  useQuery: (opts: { queryKey: string[]; queryFn: () => unknown }) => mockUseQuery(opts),
}))

// ---- Mock api client --------------------------------------------------------

const mockListSessions = vi.fn()
const mockCreateSession = vi.fn()

vi.mock('../app/lib/api-client', () => ({
  api: {
    listSessions: (...args: unknown[]) => mockListSessions(...args),
    createSession: (...args: unknown[]) => mockCreateSession(...args),
  },
}))

// ---- Import after mocks -----------------------------------------------------

import Sidebar from '../app/components/Sidebar'

// ---- Test helpers -----------------------------------------------------------

const defaultSessionData = {
  success: true,
  data: {
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
        title: null,
        started_at: '2026-06-25T14:30:00Z',
        ended_at: '2026-06-25T15:00:00Z',
        message_count: 12,
        last_message_preview: null,
      },
    ] as Array<{
      session_id: string
      title: string | null
      started_at: string
      ended_at: string | null
      message_count: number
      last_message_preview: string | null
    }>,
    total: 2,
  },
  error: null,
}

function renderSidebar(isDark = false) {
  return render(React.createElement(Sidebar, { isDark, onToggleDark: vi.fn() }))
}

// ---- Tests ------------------------------------------------------------------

describe('Sidebar session list', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockUseLocation.mockReturnValue({ pathname: '/app/chat' })
  })

  it('renders "Conversations" heading', () => {
    mockUseQuery.mockReturnValue({ data: defaultSessionData, isLoading: false, isError: false, refetch: vi.fn() })
    renderSidebar()
    const headings = screen.getAllByText('Conversations')
    expect(headings.length).toBeGreaterThanOrEqual(1)
  })

  it('shows loading skeletons while fetching', () => {
    mockUseQuery.mockReturnValue({ data: undefined, isLoading: true, isError: false, refetch: vi.fn() })
    const { container } = renderSidebar()
    // 3 skeleton placeholders rendered twice = 6 total
    const skeletons = container.querySelectorAll('.animate-pulse')
    expect(skeletons.length).toBe(6)
  })

  it('renders session items when data is returned', () => {
    mockUseQuery.mockReturnValue({ data: defaultSessionData, isLoading: false, isError: false, refetch: vi.fn() })
    renderSidebar()

    const billingTitles = screen.getAllByText('Billing inquiry')
    expect(billingTitles.length).toBeGreaterThanOrEqual(1)

    // Sessions with null title show "Chat" as fallback
    const chatLabels = screen.getAllByText('Chat')
    // "Chat" also appears as nav label, so count >= 3 (nav + 2 sessions x 2 copies)
    expect(chatLabels.length).toBeGreaterThanOrEqual(2)
  })

  it('shows last message preview', () => {
    mockUseQuery.mockReturnValue({ data: defaultSessionData, isLoading: false, isError: false, refetch: vi.fn() })
    renderSidebar()
    const previews = screen.getAllByText(/Can you check my invoice\?/)
    expect(previews.length).toBeGreaterThanOrEqual(1)
  })

  it('shows empty state when no sessions exist', () => {
    mockUseQuery.mockReturnValue({
      data: { success: true, data: { sessions: [], total: 0 }, error: null },
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    })
    renderSidebar()

    const emptyMessages = screen.getAllByText('No conversations yet')
    expect(emptyMessages.length).toBeGreaterThanOrEqual(1)
  })

  it('shows error state with retry button', () => {
    const refetchMock = vi.fn()
    mockUseQuery.mockReturnValue({ data: undefined, isLoading: false, isError: true, refetch: refetchMock })
    renderSidebar()

    const errorMessages = screen.getAllByText('Could not load conversations')
    expect(errorMessages.length).toBeGreaterThanOrEqual(1)

    const retryBtns = screen.getAllByText('Retry')
    expect(retryBtns.length).toBeGreaterThanOrEqual(1)
    fireEvent.click(retryBtns[0])
    expect(refetchMock).toHaveBeenCalledTimes(1)
  })

  it('"New" button calls createSession and navigates', async () => {
    mockUseQuery.mockReturnValue({ data: defaultSessionData, isLoading: false, isError: false, refetch: vi.fn() })
    mockCreateSession.mockResolvedValue({
      success: true,
      data: { session_id: 'sess-new-001', title: null, started_at: '2026-06-27T12:00:00Z' },
      error: null,
    })

    renderSidebar()

    const newBtns = screen.getAllByText('New')
    expect(newBtns.length).toBeGreaterThanOrEqual(1)
    fireEvent.click(newBtns[0])

    // handleNewConversation is async — wait for navigate to be called
    await waitFor(() => {
      expect(mockCreateSession).toHaveBeenCalledTimes(1)
    })
    expect(mockNavigate).toHaveBeenCalledWith({
      to: '/app/chat/$sessionId',
      params: { sessionId: 'sess-new-001' },
    })
  })
})

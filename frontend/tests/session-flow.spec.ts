/**
 * Playwright E2E tests for the session-based chat flow.
 *
 * These tests mock all API responses to avoid depending on a running backend.
 * They verify navigation, message sending, persistence across refresh,
 * session switching, and new conversation creation.
 *
 * Follows patterns from VoicePage.test.tsx:
 *   - test.describe wrapper
 *   - page.addInitScript for auth setup
 *   - page.route() for API interception
 *   - page.goto() / waitForURL() / getByText() / getByRole()
 */

import { test, expect } from '@playwright/test'

// ---------------------------------------------------------------------------
// Constants — mock session IDs and data shapes
// ---------------------------------------------------------------------------

/** JWT with sub=c63d2f89-9aa3-4157-8205-a7d6cfc23207 (matches default mock customerId) */
const MOCK_JWT =
  'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.' +
  'eyJzdWIiOiJjNjNkMmY4OS05YWEzLTQxNTctODIwNS1hN2Q2Y2ZjMjMyMDcifQ==.' +
  'fake'

const SESSION_1 = 'session-001-test'
const SESSION_2 = 'session-002-test'
const SESSION_NEW = 'session-003-new'

const MOCK_SESSIONS_LIST = {
  success: true,
  data: {
    sessions: [
      {
        session_id: SESSION_1,
        title: 'Billing question',
        started_at: '2026-06-27T10:00:00Z',
        ended_at: null,
        message_count: 2,
        last_message_preview: 'Can you help with my bill?',
      },
      {
        session_id: SESSION_2,
        title: 'Support ticket',
        started_at: '2026-06-26T14:00:00Z',
        ended_at: null,
        message_count: 4,
        last_message_preview: 'Thanks for the help',
      },
    ],
    total: 2,
  },
}

const MOCK_MESSAGES_SESSION_1 = {
  success: true,
  data: {
    session_id: SESSION_1,
    title: 'Billing question',
    messages: [
      {
        id: 'msg-1',
        role: 'user',
        content: 'Can you help with my bill?',
        created_at: '2026-06-27T10:00:00Z',
        tool_calls: null,
      },
      {
        id: 'msg-2',
        role: 'assistant',
        content: 'I would be happy to help with your billing question!',
        created_at: '2026-06-27T10:00:05Z',
        tool_calls: null,
      },
    ],
  },
}

const MOCK_MESSAGES_SESSION_2 = {
  success: true,
  data: {
    session_id: SESSION_2,
    title: 'Support ticket',
    messages: [
      {
        id: 'msg-3',
        role: 'user',
        content: 'I have a support ticket issue',
        created_at: '2026-06-26T14:00:00Z',
        tool_calls: null,
      },
      {
        id: 'msg-4',
        role: 'assistant',
        content: 'Let me look up your support tickets.',
        created_at: '2026-06-26T14:00:05Z',
        tool_calls: null,
      },
    ],
  },
}

const MOCK_EMPTY_MESSAGES = {
  success: true,
  data: {
    session_id: SESSION_NEW,
    title: null,
    messages: [],
  },
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Build an SSE response body for the /api/v1/chat/stream endpoint. */
function buildStreamResponse(userMessage: string): string {
  const response = `I received your message: "${userMessage}". Based on your account, you are on the Enterprise Plus plan. Your subscription is active and auto-renews.`
  const lines = [
    'data: {"stage":"thinking"}',
    'data: {"stage":"intent","label":"general_inquiry"}',
    'data: {"stage":"tools_selected","tools":["get_customer_subscription"]}',
    'data: {"stage":"tool_done","tool":"get_customer_subscription","ok":true}',
    'data: {"stage":"reasoning"}',
    `data: ${JSON.stringify({
      stage: 'done',
      response,
      tool_calls_made: ['get_customer_subscription'],
      evidence: { source: 'customer_profile', confidence: 0.94 },
    })}`,
    '', // trailing newline
  ]
  return lines.join('\n')
}

/**
 * Register API route handlers suitable for the basic happy-path tests.
 *
 * POST /api/v1/chat/sessions       - creates SESSION_1
 * GET  /api/v1/chat/sessions       - returns MOCK_SESSIONS_LIST
 * GET  /api/v1/chat/sessions/{id}/messages - returns per-session messages
 * POST /api/v1/chat/stream         - returns SSE with mock response
 */
async function setupDefaultRoutes(page: import('@playwright/test').Page) {
  // ---- Sessions (POST = create, GET = list) ----
  await page.route('**/api/v1/chat/sessions', async (route) => {
    if (route.request().method() === 'POST') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          success: true,
          data: {
            session_id: SESSION_1,
            title: null,
            started_at: new Date().toISOString(),
          },
        }),
      })
    } else {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(MOCK_SESSIONS_LIST),
      })
    }
  })

  // ---- Session messages ----
  await page.route('**/api/v1/chat/sessions/*/messages', async (route) => {
    const url = route.request().url()
    let body: unknown
    if (url.includes(SESSION_1)) {
      body = MOCK_MESSAGES_SESSION_1
    } else if (url.includes(SESSION_2)) {
      body = MOCK_MESSAGES_SESSION_2
    } else {
      body = MOCK_EMPTY_MESSAGES
    }
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(body),
    })
  })

  // ---- Chat stream (SSE) ----
  await page.route('**/api/v1/chat/stream', async (route) => {
    let userMessage = ''
    try {
      const json = route.request().postDataJSON()
      userMessage = json?.message ?? ''
    } catch {
      // ignore parse errors
    }
    await route.fulfill({
      status: 200,
      contentType: 'text/event-stream',
      body: buildStreamResponse(userMessage),
    })
  })
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

test.describe('Session Flow', () => {
  test.beforeEach(async ({ page }) => {
    // Set JWT before any page script runs so requireAuth() passes
    await page.addInitScript((jwt: string) => {
      localStorage.setItem('jwt', jwt)
    }, MOCK_JWT)
  })

  // -----------------------------------------------------------------------
  // Test 1 — Navigate to /app/chat → redirect to /app/chat/{sessionId}
  // -----------------------------------------------------------------------
  test('navigates to /app/chat and redirects to new session URL', async ({ page }) => {
    await setupDefaultRoutes(page)

    await page.goto('/app/chat')

    // The router's beforeLoad creates a new session (POST) and redirects
    await page.waitForURL(/\/app\/chat\/session-001-test/, { timeout: 15000 })

    // The chat page should render with the hardcoded welcome message
    await expect(page.getByText(/Good day\. This is EVA/i)).toBeVisible({ timeout: 10000 })
  })

  // -----------------------------------------------------------------------
  // Test 2 — Send a message, wait for response
  // -----------------------------------------------------------------------
  test('sends a message and receives a response via stream', async ({ page }) => {
    await setupDefaultRoutes(page)
    await page.goto('/app/chat')
    await page.waitForURL(/\/app\/chat\/session-001-test/, { timeout: 15000 })
    await expect(page.getByText(/Good day\. This is EVA/i)).toBeVisible({ timeout: 10000 })

    // Type a message
    const textarea = page.getByPlaceholder(/Type your message/i)
    await expect(textarea).toBeVisible({ timeout: 5000 })
    await textarea.fill('What plan am I on?')

    // Click send
    const sendButton = page.getByRole('button', { name: /Send message/i })
    await sendButton.click()

    // Wait for the SSE response to appear
    await expect(page.getByText(/Enterprise Plus/i)).toBeVisible({ timeout: 10000 })
  })

  // -----------------------------------------------------------------------
  // Test 3 — Refresh page, verify messages still visible
  // -----------------------------------------------------------------------
  test('persists messages after page refresh', async ({ page }) => {
    await setupDefaultRoutes(page)
    await page.goto('/app/chat')
    await page.waitForURL(/\/app\/chat\/session-001-test/, { timeout: 15000 })
    await expect(page.getByText(/Good day\. This is EVA/i)).toBeVisible({ timeout: 10000 })

    // Refresh — the mock for GET messages returns the persisted messages
    await page.reload()
    await page.waitForURL(/\/app\/chat\/session-001-test/, { timeout: 15000 })

    // The API-backed messages should now be visible (loaded via getSessionMessages)
    await expect(page.getByText('Can you help with my bill?')).toBeVisible({ timeout: 10000 })
    await expect(page.getByText('I would be happy to help')).toBeVisible({ timeout: 10000 })
  })

  // -----------------------------------------------------------------------
  // Test 4 & 5 — Navigate to different session via sidebar, verify messages
  // -----------------------------------------------------------------------
  test('navigates to a different session via sidebar and shows its messages', async ({ page }) => {
    await setupDefaultRoutes(page)
    await page.goto('/app/chat')
    await page.waitForURL(/\/app\/chat\/session-001-test/, { timeout: 15000 })
    await expect(page.getByText(/Good day\. This is EVA/i)).toBeVisible({ timeout: 10000 })

    // Wait for the sidebar to finish loading the sessions list
    await expect(page.getByText('Support ticket')).toBeVisible({ timeout: 10000 })

    // Click the "Support ticket" session in the sidebar
    await page.getByText('Support ticket').click()

    // Should navigate to the second session
    await page.waitForURL(/\/app\/chat\/session-002-test/, { timeout: 15000 })

    // The chat page should now show the messages for that session
    await expect(page.getByText('I have a support ticket issue')).toBeVisible({ timeout: 10000 })
    await expect(page.getByText('Let me look up your support tickets')).toBeVisible({ timeout: 10000 })
  })

  // -----------------------------------------------------------------------
  // Test 6 & 7 — Create new conversation via sidebar "New" button
  // -----------------------------------------------------------------------
  test('creates a new conversation via sidebar button and shows welcome message', async ({ page }) => {
    // We need a stateful mock: the first POST creates SESSION_1 (router redirect),
    // the second POST (from "New" button) creates SESSION_NEW.
    let createCounter = 0

    await page.route('**/api/v1/chat/sessions', async (route) => {
      if (route.request().method() === 'POST') {
        createCounter++
        const sessionId =
          createCounter === 1 ? SESSION_1 : SESSION_NEW
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            success: true,
            data: {
              session_id: sessionId,
              title: null,
              started_at: new Date().toISOString(),
            },
          }),
        })
      } else {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(MOCK_SESSIONS_LIST),
        })
      }
    })

    // Messages: SESSION_1 has messages, SESSION_NEW is empty
    await page.route('**/api/v1/chat/sessions/*/messages', async (route) => {
      const url = route.request().url()
      if (url.includes(SESSION_NEW)) {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(MOCK_EMPTY_MESSAGES),
        })
      } else if (url.includes(SESSION_2)) {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(MOCK_MESSAGES_SESSION_2),
        })
      } else {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(MOCK_MESSAGES_SESSION_1),
        })
      }
    })

    // Stream endpoint (for completeness, though we don't send a message here)
    await page.route('**/api/v1/chat/stream', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'text/event-stream',
        body: buildStreamResponse(''),
      })
    })

    // Navigate to /app/chat → redirects to SESSION_1
    await page.goto('/app/chat')
    await page.waitForURL(/\/app\/chat\/session-001-test/, { timeout: 15000 })
    await expect(page.getByText(/Good day\. This is EVA/i)).toBeVisible({ timeout: 10000 })

    // Click "New" in the sidebar
    const newButton = page.getByRole('button', { name: /New/i })
    await expect(newButton).toBeVisible({ timeout: 5000 })
    await newButton.click()

    // Should navigate to the new empty session
    await page.waitForURL(/\/app\/chat\/session-003-new/, { timeout: 15000 })

    // Verify welcome message is shown for the empty session (no API messages to replace it)
    await expect(page.getByText(/Good day\. This is EVA/i)).toBeVisible({ timeout: 10000 })
  })
})

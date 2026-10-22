/**
 * Session handling: in-memory access token, refresh-on-401, single-flight refresh.
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'

const REFRESH = 'http://localhost:8000/api/v1/auth/refresh'
const API = 'http://localhost:8000/api/v1/customers/c1'

function res(status: number, body: unknown = {}) {
  return Promise.resolve({ ok: status < 400, status, json: () => Promise.resolve(body) } as Response)
}

async function freshModule() {
  vi.resetModules() // module-level accessToken starts as null each test
  return import('../app/lib/api-client')
}

const authHeader = (call: unknown[]) =>
  ((call[1] as RequestInit).headers as Record<string, string>).Authorization

describe('authFetch', () => {
  beforeEach(() => {
    window.history.replaceState({}, '', '/app/chat')
  })

  it('restores the session from the refresh cookie, then sends the bearer token', async () => {
    const fetchMock = vi.fn((url: string) => (url === REFRESH ? res(200, { access_token: 'A1' }) : res(200)))
    globalThis.fetch = fetchMock as unknown as typeof fetch
    const { authFetch } = await freshModule()

    await authFetch(API)

    expect(fetchMock.mock.calls.map((c) => c[0])).toEqual([REFRESH, API])
    expect(authHeader(fetchMock.mock.calls[1])).toBe('Bearer A1')
  })

  it('on 401 refreshes once and retries with the new token', async () => {
    let tokens = ['A1', 'A2']
    let apiCalls = 0
    const fetchMock = vi.fn((url: string) =>
      url === REFRESH ? res(200, { access_token: tokens.shift() }) : res(apiCalls++ === 0 ? 401 : 200),
    )
    globalThis.fetch = fetchMock as unknown as typeof fetch
    const { authFetch } = await freshModule()

    const r = await authFetch(API)

    expect(r.status).toBe(200)
    expect(fetchMock.mock.calls.map((c) => c[0])).toEqual([REFRESH, API, REFRESH, API])
    expect(authHeader(fetchMock.mock.calls[3])).toBe('Bearer A2')
  })

  it('concurrent callers share a single refresh request', async () => {
    const fetchMock = vi.fn((url: string) => (url === REFRESH ? res(200, { access_token: 'A1' }) : res(200)))
    globalThis.fetch = fetchMock as unknown as typeof fetch
    const { authFetch } = await freshModule()

    await Promise.all([authFetch(API), authFetch(API), authFetch(API)])

    expect(fetchMock.mock.calls.filter((c) => c[0] === REFRESH)).toHaveLength(1)
  })

  it('sends the user to sign in when the refresh cookie is expired', async () => {
    const assign = vi.fn()
    Object.defineProperty(window, 'location', { value: { ...window.location, pathname: '/app/chat', assign }, writable: true })
    globalThis.fetch = vi.fn(() => res(401)) as unknown as typeof fetch
    const { authFetch, hasSession } = await freshModule()

    await authFetch(API)

    expect(assign).toHaveBeenCalledWith('/')
    expect(hasSession()).toBe(false)
  })
})

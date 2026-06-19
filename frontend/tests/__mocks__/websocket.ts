/**
 * MockWebSocket — drop-in test double for the browser WebSocket API.
 *
 * Replaces global.WebSocket in unit tests so no real network connection
 * is opened.  The test controls what the server sends by calling
 * ``instance.simulateMessage(data)`` and inspects outgoing messages via
 * ``instance.sent``.
 *
 * Usage:
 *   import { MockWebSocket, installMockWebSocket } from './__mocks__/websocket'
 *
 *   let wsInstance: MockWebSocket
 *   beforeEach(() => { wsInstance = installMockWebSocket() })
 *   afterEach(() => { global.WebSocket = originalWebSocket })
 */

export type ReadyState = 0 | 1 | 2 | 3

export class MockWebSocket extends EventTarget {
  static readonly CONNECTING = 0
  static readonly OPEN = 1
  static readonly CLOSING = 2
  static readonly CLOSED = 3

  readonly url: string
  readonly protocol: string
  readyState: ReadyState = MockWebSocket.CONNECTING
  binaryType: BinaryType = 'blob'

  /** All messages sent by the client (hook/component under test). */
  sent: string[] = []

  onopen: ((ev: Event) => void) | null = null
  onclose: ((ev: CloseEvent) => void) | null = null
  onmessage: ((ev: MessageEvent) => void) | null = null
  onerror: ((ev: Event) => void) | null = null

  constructor(url: string, protocol?: string | string[]) {
    super()
    this.url = url
    this.protocol = Array.isArray(protocol) ? protocol[0] ?? '' : protocol ?? ''

    // Simulate async connection open
    queueMicrotask(() => {
      this.readyState = MockWebSocket.OPEN
      const ev = new Event('open')
      this.dispatchEvent(ev)
      this.onopen?.(ev)
    })
  }

  send(data: string | ArrayBuffer | Blob): void {
    if (this.readyState !== MockWebSocket.OPEN) {
      throw new DOMException('WebSocket is not open', 'InvalidStateError')
    }
    this.sent.push(typeof data === 'string' ? data : '[binary]')
  }

  close(code?: number, reason?: string): void {
    if (this.readyState === MockWebSocket.CLOSED) return
    this.readyState = MockWebSocket.CLOSING
    queueMicrotask(() => {
      this.readyState = MockWebSocket.CLOSED
      const ev = new CloseEvent('close', { code: code ?? 1000, reason: reason ?? '', wasClean: true })
      this.dispatchEvent(ev)
      this.onclose?.(ev)
    })
  }

  /** Simulate a message arriving from the server. */
  simulateMessage(data: string): void {
    const ev = new MessageEvent('message', { data })
    this.dispatchEvent(ev)
    this.onmessage?.(ev)
  }

  /** Simulate a server-side close. */
  simulateClose(code = 1000, reason = ''): void {
    this.readyState = MockWebSocket.CLOSED
    const ev = new CloseEvent('close', { code, reason, wasClean: true })
    this.dispatchEvent(ev)
    this.onclose?.(ev)
  }

  /** Simulate a connection error. */
  simulateError(): void {
    const ev = new Event('error')
    this.dispatchEvent(ev)
    this.onerror?.(ev)
  }
}

let _lastInstance: MockWebSocket | null = null
const _originalWebSocket = globalThis.WebSocket

/**
 * Replace ``globalThis.WebSocket`` with ``MockWebSocket`` and return a
 * reference to the most recently constructed instance.
 *
 * Call this in ``beforeEach`` and restore in ``afterEach``:
 *
 *   afterEach(() => restoreMockWebSocket())
 */
export function installMockWebSocket(): { getInstance: () => MockWebSocket | null } {
  _lastInstance = null
  const ctor = function (url: string, protocol?: string | string[]) {
    _lastInstance = new MockWebSocket(url, protocol)
    return _lastInstance
  }
  Object.assign(ctor, MockWebSocket)
  ;(globalThis as unknown as { WebSocket: unknown }).WebSocket = ctor
  return { getInstance: () => _lastInstance }
}

export function restoreMockWebSocket(): void {
  ;(globalThis as unknown as { WebSocket: unknown }).WebSocket = _originalWebSocket
  _lastInstance = null
}

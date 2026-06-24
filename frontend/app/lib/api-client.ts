// ---------------------------------------------------------------------------
// Typed API client for the Enterprise Voice Agent backend
// All endpoints return ToolResult<T> = { success: boolean, data: T | null, error: string | null }
// ---------------------------------------------------------------------------

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

// ---- Types -----------------------------------------------------------------

export interface ToolResult<T> {
  success: boolean
  data: T | null
  error: string | null
}

export interface ChatRequest {
  message: string
  customer_id: string
}

export interface ChatResponse {
  response: string
  evidence: Record<string, unknown> | null
  reasoning_trace: Record<string, unknown> | null
  tool_calls_made: string[]
}

export interface CustomerProfile {
  id: string
  name: string
  email: string
  phone: string
  created_at: string
  tier: string
  status: string
  active_scenario: string | null
  [key: string]: unknown
}

export interface Subscription {
  id: string
  customer_id: string
  plan: string
  status: string
  start_date: string
  end_date: string | null
  auto_renew: boolean
  amount: number
  currency: string
  [key: string]: unknown
}

export interface Ticket {
  id: string
  customer_id: string
  subject: string
  description: string
  status: string
  priority: string
  created_at: string
  updated_at: string
  [key: string]: unknown
}

export interface TicketStatus {
  id: string
  status: string
  priority: string
  assignee: string | null
  updated_at: string
  [key: string]: unknown
}

export interface BillingRecord {
  id: string
  customer_id: string
  amount: number
  currency: string
  description: string
  date: string
  status: string
  [key: string]: unknown
}

export interface RefundRecord {
  id: string
  customer_id: string
  original_transaction_id: string
  amount: number
  currency: string
  reason: string
  date: string
  status: string
  [key: string]: unknown
}

export interface UsageAnalytics {
  metric_name: string
  period: string
  data_points: { date: string; value: number }[]
  total: number
  [key: string]: unknown
}

export interface KnowledgeResult {
  title: string
  content: string
  relevance: number
  source: string
  [key: string]: unknown
}

export interface KnowledgeSearchRequest {
  query: string
}

// ---- Helpers ---------------------------------------------------------------

class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    public body: unknown = null,
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

async function request<T>(
  method: string,
  path: string,
  body?: unknown,
  params?: Record<string, string | undefined>,
): Promise<ToolResult<T>> {
  const url = new URL(`${API_BASE}${path}`)
  if (params) {
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null) url.searchParams.set(k, v)
    })
  }

  const headers: Record<string, string> = {}
  const token = typeof localStorage !== 'undefined' ? localStorage.getItem('jwt') : null
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }
  if (body !== undefined) {
    headers['Content-Type'] = 'application/json'
  }

  try {
    const res = await fetch(url.toString(), {
      method,
      headers,
      body: body !== undefined ? JSON.stringify(body) : undefined,
      signal: AbortSignal.timeout(15000),
    })

    if (!res.ok) {
      throw new ApiError(res.status, `HTTP ${res.status}: ${res.statusText}`)
    }

    const result: ToolResult<T> = await res.json()
    return result
  } catch (err) {
    if (err instanceof ApiError) throw err
    // Network error / backend unreachable
    return {
      success: false,
      data: null,
      error: err instanceof Error ? err.message : 'Network error',
    }
  }
}

function get<T>(path: string, params?: Record<string, string | undefined>): Promise<ToolResult<T>> {
  return request<T>('GET', path, undefined, params)
}

function post<T>(path: string, body: unknown): Promise<ToolResult<T>> {
  return request<T>('POST', path, body)
}

// ---- Mock data (used when backend is unreachable) ---------------------------

const MOCK_CUSTOMER_ID = 'c63d2f89-9aa3-4157-8205-a7d6cfc23207'

const mockProfile: CustomerProfile = {
  id: MOCK_CUSTOMER_ID,
  name: 'Acme Corp',
  email: 'contact@acmecorp.com',
  phone: '+1-555-0100',
  created_at: '2023-06-15T08:00:00Z',
  tier: 'enterprise',
  status: 'active',
  active_scenario: null,
}

const mockSubscription: Subscription = {
  id: 'sub_001',
  customer_id: MOCK_CUSTOMER_ID,
  plan: 'Enterprise Plus',
  status: 'active',
  start_date: '2024-01-01T00:00:00Z',
  end_date: null,
  auto_renew: true,
  amount: 2999.00,
  currency: 'USD',
}

const mockTickets: Ticket[] = [
  { id: 'tkt_001', customer_id: MOCK_CUSTOMER_ID, subject: 'Login issue', description: 'Unable to login via SSO', status: 'open', priority: 'high', created_at: '2026-06-08T10:00:00Z', updated_at: '2026-06-08T14:00:00Z' },
  { id: 'tkt_002', customer_id: MOCK_CUSTOMER_ID, subject: 'Billing discrepancy', description: 'Overcharged on June invoice', status: 'in_progress', priority: 'medium', created_at: '2026-06-05T09:00:00Z', updated_at: '2026-06-09T11:00:00Z' },
  { id: 'tkt_003', customer_id: MOCK_CUSTOMER_ID, subject: 'Feature request: dark mode', description: 'Would like dark mode support', status: 'closed', priority: 'low', created_at: '2026-05-20T16:00:00Z', updated_at: '2026-06-01T08:00:00Z' },
]

const mockBillingHistory: BillingRecord[] = [
  { id: 'inv_001', customer_id: MOCK_CUSTOMER_ID, amount: 2999.00, currency: 'USD', description: 'Enterprise Plus - June 2026', date: '2026-06-01T00:00:00Z', status: 'paid' },
  { id: 'inv_002', customer_id: MOCK_CUSTOMER_ID, amount: 2999.00, currency: 'USD', description: 'Enterprise Plus - May 2026', date: '2026-05-01T00:00:00Z', status: 'paid' },
  { id: 'inv_003', customer_id: MOCK_CUSTOMER_ID, amount: 2999.00, currency: 'USD', description: 'Enterprise Plus - Apr 2026', date: '2026-04-01T00:00:00Z', status: 'paid' },
  { id: 'inv_004', customer_id: MOCK_CUSTOMER_ID, amount: 1499.50, currency: 'USD', description: 'Add-on: Analytics Pro - June 2026', date: '2026-06-01T00:00:00Z', status: 'paid' },
]

const mockRefunds: RefundRecord[] = [
  { id: 'ref_001', customer_id: MOCK_CUSTOMER_ID, original_transaction_id: 'inv_002', amount: 199.00, currency: 'USD', reason: 'Service credit adjustment', date: '2026-05-15T00:00:00Z', status: 'completed' },
]

const mockUsageData: UsageAnalytics = {
  metric_name: 'api_calls',
  period: 'last_30_days',
  data_points: Array.from({ length: 30 }, (_, i) => ({
    date: new Date(Date.now() - (29 - i) * 86400000).toISOString().slice(0, 10),
    value: Math.floor(Math.random() * 500) + 100,
  })),
  total: 8450,
}

const mockDocsResults: KnowledgeResult[] = [
  { title: 'Getting Started Guide', content: 'Learn how to set up and configure your Enterprise Voice Agent instance...', relevance: 0.95, source: 'documentation' },
  { title: 'API Reference', content: 'Complete API reference for all endpoints including authentication, chat, and tools...', relevance: 0.88, source: 'documentation' },
  { title: 'Installation Instructions', content: 'Step-by-step guide to install the Enterprise Voice Agent on your infrastructure...', relevance: 0.82, source: 'documentation' },
]

const mockPolicyResults: KnowledgeResult[] = [
  { title: 'Data Retention Policy', content: 'Customer data is retained for the duration of the subscription plus 90 days...', relevance: 0.91, source: 'policies' },
  { title: 'SLA Agreement', content: 'Enterprise Voice Agent guarantees 99.9% uptime for paid subscriptions...', relevance: 0.87, source: 'policies' },
  { title: 'Privacy Policy', content: 'We collect and process customer data in accordance with GDPR and CCPA...', relevance: 0.85, source: 'policies' },
]

const mockChatResponse: ChatResponse = {
  response: 'I can help you with that! Based on your account, you are on the Enterprise Plus plan. Your current subscription is active and auto-renews. Would you like me to check anything specific about your billing or support tickets?',
  evidence: { source: 'customer_profile', confidence: 0.94 },
  reasoning_trace: { steps: ['identified customer', 'looked up subscription', 'formulated response'] },
  tool_calls_made: ['get_customer_subscription'],
}

// ---- Public API ------------------------------------------------------------

// ---- Voice types -----------------------------------------------------------

export interface CallSummaryResult {
  session_id: string
  conversation_summary: string
  sources_used: string[]
  reasoning_summary: string
  recommended_next_actions: string[]
}

export const api = {
  // Voice
  getCallSummary: (sessionId: string): Promise<ToolResult<CallSummaryResult>> =>
    get<CallSummaryResult>(`/api/v1/voice/summary/${encodeURIComponent(sessionId)}`),

  // Chat
  chat: (req: ChatRequest): Promise<ToolResult<ChatResponse>> =>
    post<ChatResponse>('/api/v1/chat/', req),

  // Customer profile
  customerProfile: (customerId: string): Promise<ToolResult<CustomerProfile>> =>
    get<CustomerProfile>('/api/v1/tools/customer/profile', { customer_id: customerId }),

  // Subscription
  customerSubscription: (customerId: string): Promise<ToolResult<Subscription>> =>
    get<Subscription>('/api/v1/tools/customer/subscription', { customer_id: customerId }),

  // Ticket list
  ticketList: (customerId: string): Promise<ToolResult<Ticket[]>> =>
    get<Ticket[]>('/api/v1/tools/ticket/list', { customer_id: customerId }),

  // Single ticket status
  ticketStatus: (customerId: string, ticketId: string): Promise<ToolResult<TicketStatus>> =>
    get<TicketStatus>('/api/v1/tools/ticket/status', { customer_id: customerId, ticket_id: ticketId }),

  // Billing history
  billingHistory: (customerId: string): Promise<ToolResult<BillingRecord[]>> =>
    get<BillingRecord[]>('/api/v1/tools/billing/history', { customer_id: customerId }),

  // Refunds
  billingRefunds: (customerId: string): Promise<ToolResult<RefundRecord[]>> =>
    get<RefundRecord[]>('/api/v1/tools/billing/refunds', { customer_id: customerId }),

  // Usage analytics
  usageAnalytics: (customerId: string, metricName?: string): Promise<ToolResult<UsageAnalytics>> =>
    get<UsageAnalytics>('/api/v1/tools/analytics/usage', { customer_id: customerId, metric_name: metricName }),

  // Knowledge search
  knowledgeDocs: (query: string): Promise<ToolResult<KnowledgeResult[]>> =>
    post<KnowledgeResult[]>('/api/v1/tools/knowledge/documentation', { query }),

  knowledgePolicies: (query: string): Promise<ToolResult<KnowledgeResult[]>> =>
    post<KnowledgeResult[]>('/api/v1/tools/knowledge/policies', { query }),

  applyScenario: (scenarioId: string): Promise<ToolResult<{ scenario_id: string; active_scenario: string; customer_id: string }>> =>
    post('/api/v1/demo/apply-scenario', { scenario_id: scenarioId }),
}

// ---- Mock data helpers -----------------------------------------------------

export const mock = {
  get customerId() {
    const token = typeof localStorage !== 'undefined' ? localStorage.getItem('jwt') : null;
    if (!token) return MOCK_CUSTOMER_ID;
    try {
      const payload = JSON.parse(atob(token.split('.')[1]));
      return payload.sub || MOCK_CUSTOMER_ID;
    } catch (e) {
      return MOCK_CUSTOMER_ID;
    }
  },
  profile: mockProfile,
  subscription: mockSubscription,
  tickets: mockTickets,
  billingHistory: mockBillingHistory,
  refunds: mockRefunds,
  usageData: mockUsageData,
  docsResults: mockDocsResults,
  policyResults: mockPolicyResults,
  chatResponse: mockChatResponse,
  applyScenarioResponse: { scenario_id: 'billing_dispute', active_scenario: 'billing_dispute', customer_id: MOCK_CUSTOMER_ID },
}

export function isMockData<T>(result: ToolResult<T> | undefined): boolean {
  return result ? !result.success && result.error !== null && result.error.includes('Network error') : false
}


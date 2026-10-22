import { useState } from 'react'
import { Outlet, useLocation, useNavigate } from '@tanstack/react-router'
import { useQuery } from '@tanstack/react-query'
import { MessageSquare, Mic, User, Sun, Moon, LogOut, X } from 'lucide-react'
import { api, mock, logout } from '../lib/api-client'
import { useAppContext } from './__root'
import AccountSummary from '../components/AccountSummary'

const navTabs = [
  { href: '/app/chat', label: 'Chat', icon: MessageSquare },
  { href: '/app/voice', label: 'Voice', icon: Mic },
]

export function AppShell() {
  const { setBackendOffline, isDark, onToggleDark } = useAppContext()
  const customerId = mock.customerId
  const location = useLocation()
  const navigate = useNavigate()

  const [contextOpen, setContextOpen] = useState(false)

  const profileQuery = useQuery({
    queryKey: ['customerProfile', customerId],
    queryFn: () => api.customerProfile(customerId),
  })

  const subscriptionQuery = useQuery({
    queryKey: ['customerSubscription', customerId],
    queryFn: () => api.customerSubscription(customerId),
  })

  const ticketsQuery = useQuery({
    queryKey: ['ticketList', customerId],
    queryFn: () => api.ticketList(customerId),
  })

  const billingQuery = useQuery({
    queryKey: ['billingHistory', customerId],
    queryFn: () => api.billingHistory(customerId),
  })

  const analyticsQuery = useQuery({
    queryKey: ['usageAnalytics', customerId],
    queryFn: () => api.usageAnalytics(customerId),
  })

  if ([profileQuery, subscriptionQuery, ticketsQuery, billingQuery, analyticsQuery].some(
    q => q.isError
  )) {
    setBackendOffline(true)
  }

  const accountSummaryProps = {
    profile: profileQuery.data?.data ?? null,
    subscription: subscriptionQuery.data?.data ?? null,
    tickets: ticketsQuery.data?.data ?? null,
    billing: billingQuery.data?.data ?? null,
    analytics: analyticsQuery.data?.data ?? null,
    isLoading: profileQuery.isLoading,
  }

  return (
    <div className="flex flex-col md:flex-row h-dvh overflow-hidden">
      {/* Left panel — main content rendered by child route */}
      <div className="flex-1 flex flex-col overflow-hidden pb-16 md:pb-0">
        <Outlet />
      </div>

      {/* Right panel — account data sidebar (hidden on mobile) */}
      <div className="hidden md:block w-[380px] flex-shrink-0 border-l border-hairline dark:border-white/5 overflow-y-auto bg-surface-stone dark:bg-surface-dark-elevated">
        <AccountSummary {...accountSummaryProps} />
      </div>

      {/* ── Mobile bottom tab bar ──────────────────────────────────────── */}
      <nav
        className="md:hidden fixed bottom-0 inset-x-0 z-40 bg-surface-white dark:bg-surface-dark-elevated border-t border-hairline dark:border-white/10 flex items-stretch"
        style={{ paddingBottom: 'env(safe-area-inset-bottom, 0px)' }}
      >
        {/* Chat + Voice tabs */}
        {navTabs.map(({ href, label, icon: Icon }) => {
          const isActive = location.pathname === href
          return (
            <button
              key={href}
              onClick={() => { void navigate({ to: href }) }}
              className={`relative flex-1 flex flex-col items-center justify-center gap-0.5 py-2.5 min-h-[56px] transition-colors ${
                isActive
                  ? 'text-ink dark:text-white'
                  : 'text-muted-slate dark:text-gray-500 hover:text-ink dark:hover:text-gray-300'
              }`}
              aria-label={label}
            >
              <Icon size={22} strokeWidth={isActive ? 2.5 : 1.8} />
              <span className="text-[10px] font-medium tracking-wide">{label}</span>
              {isActive && (
                <span className="absolute bottom-1 w-1 h-1 rounded-full bg-brand-coral" />
              )}
            </button>
          )
        })}

        {/* Context tab — opens AccountSummary sheet */}
        <button
          onClick={() => setContextOpen(true)}
          className={`relative flex-1 flex flex-col items-center justify-center gap-0.5 py-2.5 min-h-[56px] transition-colors ${
            contextOpen
              ? 'text-ink dark:text-white'
              : 'text-muted-slate dark:text-gray-500 hover:text-ink dark:hover:text-gray-300'
          }`}
          aria-label="Account context"
        >
          <User size={22} strokeWidth={contextOpen ? 2.5 : 1.8} />
          <span className="text-[10px] font-medium tracking-wide">Context</span>
        </button>

        {/* Dark mode toggle */}
        <button
          onClick={onToggleDark}
          className="flex-1 flex flex-col items-center justify-center gap-0.5 py-2.5 min-h-[56px] text-muted-slate dark:text-gray-500 hover:text-ink dark:hover:text-gray-300 transition-colors"
          aria-label="Toggle dark mode"
        >
          {isDark ? <Sun size={22} strokeWidth={1.8} /> : <Moon size={22} strokeWidth={1.8} />}
          <span className="text-[10px] font-medium tracking-wide">{isDark ? 'Light' : 'Dark'}</span>
        </button>

        {/* Logout */}
        <button
          onClick={async () => {
            await logout()
            void navigate({ to: '/', replace: true })
          }}
          className="flex-1 flex flex-col items-center justify-center gap-0.5 py-2.5 min-h-[56px] text-muted-slate dark:text-gray-500 hover:text-red-500 dark:hover:text-red-400 transition-colors"
          aria-label="Logout"
        >
          <LogOut size={22} strokeWidth={1.8} />
          <span className="text-[10px] font-medium tracking-wide">Logout</span>
        </button>
      </nav>

      {/* ── Mobile context sheet backdrop ─────────────────────────────── */}
      {contextOpen && (
        <div
          className="md:hidden fixed inset-0 bg-black/40 z-40"
          onClick={() => setContextOpen(false)}
        />
      )}

      {/* ── Mobile context sheet ───────────────────────────────────────── */}
      <div
        className={`md:hidden fixed inset-x-0 bottom-0 z-50 bg-surface-white dark:bg-surface-dark-elevated rounded-t-2xl shadow-xl transform transition-transform duration-300 ${
          contextOpen ? 'translate-y-0' : 'translate-y-full'
        }`}
        style={{ maxHeight: '82vh', paddingBottom: 'env(safe-area-inset-bottom, 0px)' }}
      >
        {/* Sheet header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-hairline dark:border-white/5">
          <div className="flex items-center gap-2">
            <User size={16} className="text-brand-coral" />
            <span className="font-semibold text-sm text-ink dark:text-white">Account Context</span>
          </div>
          <button
            onClick={() => setContextOpen(false)}
            className="p-2 rounded-sm hover:bg-surface-stone dark:hover:bg-white/5 transition-colors"
            aria-label="Close"
          >
            <X size={18} className="text-muted-slate" />
          </button>
        </div>

        {/* Scrollable AccountSummary content */}
        <div className="overflow-y-auto" style={{ maxHeight: 'calc(82vh - 65px)' }}>
          <AccountSummary {...accountSummaryProps} />
        </div>
      </div>
    </div>
  )
}

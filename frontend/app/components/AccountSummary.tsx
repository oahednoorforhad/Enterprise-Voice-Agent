import { CustomerProfile, Subscription, Ticket, BillingRecord, UsageAnalytics } from '../lib/api-client'
import { CreditCard, Ticket as TicketIcon, TrendingUp, User, RefreshCw } from 'lucide-react'
import DemoBadge from './DemoBadge'

interface AccountSummaryProps {
  profile: CustomerProfile | null
  subscription: Subscription | null
  tickets: Ticket[] | null
  billing: BillingRecord[] | null
  analytics: UsageAnalytics | null
  isLoading: boolean
}

export default function AccountSummary({ profile, subscription, tickets, billing, analytics, isLoading }: AccountSummaryProps) {
  if (isLoading) {
    return (
      <div className="p-6 space-y-4 animate-pulse">
        {[...Array(4)].map((_, i) => (
          <div key={i} className="h-24 bg-gray-100 dark:bg-gray-800 rounded-xl" />
        ))}
      </div>
    )
  }

  const openTickets = tickets?.filter(t => t.status === 'open' || t.status === 'in_progress') ?? []
  const latestBilling = billing?.slice(0, 3) ?? []

  return (
    <div className="p-4 space-y-4">
      {/* Demo badge */}
      <DemoBadge />

      {/* Customer info */}
      {profile && (
        <div className="card">
          <div className="card-header flex items-center gap-3">
            <div className="w-9 h-9 rounded-full bg-brand-100 dark:bg-brand-900/30 flex items-center justify-center">
              <User size={16} className="text-brand-600 dark:text-brand-400" />
            </div>
            <div className="min-w-0">
              <p className="font-semibold text-sm text-gray-900 dark:text-gray-100 truncate">{profile.name}</p>
              <p className="text-xs text-gray-500 dark:text-gray-400 truncate">{profile.email}</p>
            </div>
          </div>
          <div className="card-body">
            <div className="grid grid-cols-2 gap-2 text-xs">
              <div>
                <p className="metric-label">Tier</p>
                <p className="font-medium text-gray-800 dark:text-gray-200 capitalize">{profile.tier ?? '—'}</p>
              </div>
              <div>
                <p className="metric-label">Status</p>
                <span className={`badge ${profile.status === 'active' ? 'badge-success' : 'badge-warning'}`}>
                  {profile.status ?? '—'}
                </span>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Subscription */}
      {subscription && (
        <div className="card">
          <div className="card-header flex items-center gap-2">
            <RefreshCw size={14} className="text-brand-500" />
            <span className="text-sm font-semibold text-gray-900 dark:text-gray-100">Subscription</span>
          </div>
          <div className="card-body grid grid-cols-2 gap-2 text-xs">
            <div>
              <p className="metric-label">Plan</p>
              <p className="font-medium text-gray-800 dark:text-gray-200 truncate">{subscription.plan}</p>
            </div>
            <div>
              <p className="metric-label">Status</p>
              <span className={`badge ${subscription.status === 'active' ? 'badge-success' : 'badge-warning'}`}>
                {subscription.status}
              </span>
            </div>
            <div>
              <p className="metric-label">Amount</p>
              <p className="font-medium text-gray-800 dark:text-gray-200">${subscription.amount?.toFixed(2)}/mo</p>
            </div>
            <div>
              <p className="metric-label">Renews</p>
              <p className="font-medium text-gray-800 dark:text-gray-200">
                {subscription.end_date ? new Date(subscription.end_date).toLocaleDateString() : '—'}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Open tickets */}
      <div className="card">
        <div className="card-header flex items-center gap-2">
          <TicketIcon size={14} className="text-amber-500" />
          <span className="text-sm font-semibold text-gray-900 dark:text-gray-100">
            Open Tickets <span className="text-xs text-gray-400 ml-1">({openTickets.length})</span>
          </span>
        </div>
        <div className="card-body space-y-2">
          {openTickets.length === 0 ? (
            <p className="text-xs text-gray-400">No open tickets</p>
          ) : openTickets.slice(0, 3).map(t => (
            <div key={t.id} className="flex items-start gap-2">
              <span className={`badge mt-0.5 flex-shrink-0 ${
                t.priority === 'high' || t.priority === 'critical' ? 'badge-error' :
                t.priority === 'medium' ? 'badge-warning' : 'badge-info'
              }`}>{t.priority}</span>
              <p className="text-xs text-gray-700 dark:text-gray-300 truncate">{t.subject || (t as any).title}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Recent billing */}
      <div className="card">
        <div className="card-header flex items-center gap-2">
          <CreditCard size={14} className="text-green-500" />
          <span className="text-sm font-semibold text-gray-900 dark:text-gray-100">Recent Billing</span>
        </div>
        <div className="card-body space-y-2">
          {latestBilling.length === 0 ? (
            <p className="text-xs text-gray-400">No billing records</p>
          ) : latestBilling.map(b => (
            <div key={b.id} className="flex items-center justify-between">
              <div className="min-w-0 mr-2">
                <p className="text-xs text-gray-700 dark:text-gray-300 truncate">{b.description}</p>
                <p className="text-[10px] text-gray-400">{b.date ? new Date(b.date).toLocaleDateString() : ''}</p>
              </div>
              <div className="text-right flex-shrink-0">
                <p className="text-xs font-medium text-gray-900 dark:text-gray-100">${b.amount?.toFixed(2)}</p>
                <span className={`badge text-[10px] ${b.status === 'paid' ? 'badge-success' : b.status === 'overdue' ? 'badge-error' : 'badge-warning'}`}>
                  {b.status}
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Usage analytics */}
      {analytics && (
        <div className="card">
          <div className="card-header flex items-center gap-2">
            <TrendingUp size={14} className="text-blue-500" />
            <span className="text-sm font-semibold text-gray-900 dark:text-gray-100">Usage</span>
          </div>
          <div className="card-body">
            <p className="text-xs text-gray-500 dark:text-gray-400 capitalize mb-1">{analytics.metric_name?.replace(/_/g, ' ')}</p>
            <p className="text-2xl font-bold text-gray-900 dark:text-gray-100">{analytics.total?.toLocaleString()}</p>
            <p className="text-[10px] text-gray-400 mt-1">{analytics.period}</p>
          </div>
        </div>
      )}
    </div>
  )
}

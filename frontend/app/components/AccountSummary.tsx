import { useState } from 'react'
import { CustomerProfile, Subscription, Ticket, BillingRecord, UsageAnalytics } from '../lib/api-client'
import { CreditCard, Ticket as TicketIcon, TrendingUp, User, RefreshCw, ChevronDown, ChevronRight } from 'lucide-react'
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
  const [expandedTickets, setExpandedTickets] = useState(new Set<string>())

  const toggleTicket = (id: string) => {
    setExpandedTickets(prev => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id); else next.add(id)
      return next
    })
  }

  if (isLoading) {
    return (
      <div className="p-5 space-y-4 animate-pulse">
        {[...Array(4)].map((_, i) => (
          <div key={i} className="h-24 bg-surface-stone dark:bg-surface-dark-elevated rounded-lg" />
        ))}
      </div>
    )
  }

  const openTickets = tickets?.filter(t => t.status === 'open' || t.status === 'in_progress') ?? []
  const latestBilling = billing?.slice(0, 3) ?? []

  return (
    <div className="p-5 space-y-4">
      {/* Demo badge */}
      <DemoBadge />

      {/* Customer info */}
      {profile && (
        <div className="card-flat">
          <div className="flex items-center gap-3 px-5 py-3.5 border-b border-hairline dark:border-white/5">
            <div className="w-9 h-9 rounded-full bg-surface-stone dark:bg-surface-dark-elevated flex items-center justify-center">
              <User size={16} className="text-muted-slate dark:text-gray-400" />
            </div>
            <div className="min-w-0">
              <p className="font-display text-heading-feature text-ink dark:text-white truncate leading-tight">{profile.name}</p>
              <p className="text-caption text-muted-slate truncate">{profile.email}</p>
            </div>
          </div>
          <div className="px-5 py-3.5">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <p className="label-mono text-[11px] mb-0.5">Tier</p>
                <p className="text-body-small font-medium text-ink dark:text-gray-100 capitalize">{profile.tier ?? '—'}</p>
              </div>
              <div>
                <p className="label-mono text-[11px] mb-0.5">Status</p>
                <span className={`chip text-[11px] py-0.5 ${profile.status === 'active' ? 'chip-green' : 'chip-amber'}`}>
                  {profile.status ?? '—'}
                </span>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Subscription */}
      {subscription && (
        <div className="card-flat">
          <div className="flex items-center gap-2 px-5 py-3.5 border-b border-hairline dark:border-white/5">
            <RefreshCw size={14} className="text-brand-coral" />
            <span className="font-display text-heading-feature text-ink dark:text-white text-sm">Subscription</span>
          </div>
          <div className="px-5 py-3.5">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <p className="label-mono text-[11px] mb-0.5">Plan</p>
                <p className="text-body-small font-medium text-ink dark:text-gray-100 truncate">{subscription.plan}</p>
              </div>
              <div>
                <p className="label-mono text-[11px] mb-0.5">Status</p>
                <span className={`chip text-[11px] py-0.5 ${subscription.status === 'active' ? 'chip-green' : 'chip-amber'}`}>
                  {subscription.status}
                </span>
              </div>
              <div>
                <p className="label-mono text-[11px] mb-0.5">Amount</p>
                <p className="text-body-small font-medium text-ink dark:text-gray-100">${subscription.amount?.toFixed(2)}/mo</p>
              </div>
              <div>
                <p className="label-mono text-[11px] mb-0.5">Renews</p>
                <p className="text-body-small font-medium text-ink dark:text-gray-100">
                  {subscription.end_date ? new Date(subscription.end_date).toLocaleDateString() : '—'}
                </p>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Tickets */}
      <div className="card-flat">
        <div className="flex items-center gap-2 px-5 py-3.5 border-b border-hairline dark:border-white/5">
          <TicketIcon size={14} className="text-brand-coral flex-shrink-0" />
          <span className="font-display text-heading-feature text-ink dark:text-white text-sm">
            Tickets <span className="text-caption text-muted-slate ml-1">({openTickets.length})</span>
          </span>
        </div>
        {openTickets.length === 0 ? (
          <div className="px-5 py-3.5">
            <p className="text-caption text-muted-slate">No open tickets</p>
          </div>
        ) : (
          <div className="divide-y divide-hairline dark:divide-gray-700/50">
            {openTickets.map(t => (
              <div key={t.id}>
                <div
                  onClick={() => toggleTicket(t.id)}
                  className="flex items-start gap-2 px-5 py-2.5 hover:bg-gray-50 dark:hover:bg-white/5 transition-colors cursor-pointer select-none"
                >
                  <span className={`chip text-[11px] py-0.5 flex-shrink-0 ${
                    t.priority === 'high' || t.priority === 'critical' ? 'chip-red' :
                    t.priority === 'medium' ? 'chip-amber' : 'chip-blue'
                  }`}>{t.priority}</span>
                  <span className="flex-1 text-caption text-ink dark:text-gray-300 leading-relaxed">{t.subject}</span>
                  {expandedTickets.has(t.id)
                    ? <ChevronDown size={12} className="text-muted-slate mt-0.5 flex-shrink-0" />
                    : <ChevronRight size={12} className="text-muted-slate mt-0.5 flex-shrink-0" />}
                </div>
                {expandedTickets.has(t.id) && (
                  <div className="px-5 pb-3 pt-0.5">
                    <p className="text-caption text-muted-slate leading-relaxed">{t.description}</p>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Recent billing */}
      <div className="card-flat">
        <div className="flex items-center gap-2 px-5 py-3.5 border-b border-hairline dark:border-white/5">
          <CreditCard size={14} className="text-brand-coral" />
          <span className="font-display text-heading-feature text-ink dark:text-white text-sm">Recent Billing</span>
        </div>
        <div className="px-5 py-3.5 space-y-2.5">
          {latestBilling.length === 0 ? (
            <p className="text-caption text-muted-slate">No billing records</p>
          ) : latestBilling.map(b => (
            <div key={b.id} className="flex items-center justify-between">
              <div className="min-w-0 mr-2">
                <p className="text-caption text-ink dark:text-gray-300 truncate">{b.description}</p>
                <p className="text-micro text-muted-slate mt-0.5">{b.date ? new Date(b.date).toLocaleDateString() : ''}</p>
              </div>
              <div className="text-right flex-shrink-0">
                <p className="text-body-small font-medium text-ink dark:text-gray-100">${(Number(b.amount) || 0).toFixed(2)}</p>
                <span className={`chip text-[11px] py-0.5 mt-0.5 ${b.status === 'paid' ? 'chip-green' : b.status === 'overdue' ? 'chip-red' : 'chip-amber'}`}>
                  {b.status}
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Usage analytics */}
      {analytics && (
        <div className="card-flat">
          <div className="flex items-center gap-2 px-5 py-3.5 border-b border-hairline dark:border-white/5">
            <TrendingUp size={14} className="text-brand-coral" />
            <span className="font-display text-heading-feature text-ink dark:text-white text-sm">Usage</span>
          </div>
          <div className="px-5 py-3.5">
            <p className="label-mono text-[11px] mb-1">{analytics.metric_name?.replace(/_/g, ' ')}</p>
            <p className="font-display text-display-product text-brand-near dark:text-white leading-none">{analytics.total?.toLocaleString()}</p>
            <p className="text-micro text-muted-slate mt-1.5">{analytics.period}</p>
          </div>
        </div>
      )}
    </div>
  )
}

import { useQuery } from '@tanstack/react-query'
import {
  User,
  Mail,
  Phone,
  Calendar,
  Shield,
  CreditCard,
  TicketCheck,
  Building2,
  MapPin,
  Globe,
  RefreshCw,
  AlertTriangle,
} from 'lucide-react'
import LoadingSpinner from '../components/LoadingSpinner'
import { api, mock, isMockData } from '../lib/api-client'
import { useAppContext } from './__root'

export function DashboardPage() {
  const { setBackendOffline } = useAppContext()

  const profileQuery = useQuery({
    queryKey: ['profile', mock.customerId],
    queryFn: () => api.customerProfile(mock.customerId),
  })

  const subscriptionQuery = useQuery({
    queryKey: ['subscription', mock.customerId],
    queryFn: () => api.customerSubscription(mock.customerId),
  })

  const ticketsQuery = useQuery({
    queryKey: ['tickets', mock.customerId],
    queryFn: () => api.ticketList(mock.customerId),
  })

  const billingQuery = useQuery({
    queryKey: ['billing', mock.customerId],
    queryFn: () => api.billingHistory(mock.customerId),
  })

  const refundsQuery = useQuery({
    queryKey: ['refunds', mock.customerId],
    queryFn: () => api.billingRefunds(mock.customerId),
  })

  // Detect offline
  if (
    [profileQuery, subscriptionQuery, ticketsQuery, billingQuery, refundsQuery].some(
      (q) => isMockData(q.data as any),
    )
  ) {
    setBackendOffline(true)
  }

  const profile = profileQuery.data?.success
    ? (profileQuery.data.data ?? mock.profile)
    : mock.profile
  const subscription = subscriptionQuery.data?.success
    ? (subscriptionQuery.data.data ?? mock.subscription)
    : mock.subscription
  const tickets = ticketsQuery.data?.success
    ? (ticketsQuery.data.data ?? mock.tickets)
    : mock.tickets
  const billing = billingQuery.data?.success
    ? (billingQuery.data.data ?? mock.billingHistory)
    : mock.billingHistory
  const refunds = refundsQuery.data?.success
    ? (refundsQuery.data.data ?? mock.refunds)
    : mock.refunds

  const isLoading =
    profileQuery.isLoading ||
    subscriptionQuery.isLoading ||
    ticketsQuery.isLoading ||
    billingQuery.isLoading

  if (isLoading) {
    return <LoadingSpinner fullPage message="Loading customer data..." />
  }

  const statusColor = (status: string) => {
    switch (status) {
      case 'active':
      case 'paid':
      case 'completed':
      case 'closed':
        return 'badge-success'
      case 'in_progress':
      case 'pending':
      case 'refunded':
        return 'badge-warning'
      case 'open':
        return 'badge-info'
      case 'cancelled':
      case 'failed':
        return 'badge-error'
      default:
        return 'badge-info'
    }
  }

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">
          Customer Dashboard
        </h1>
        <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
          Detailed view of customer profile, subscription, billing, and support
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Profile Card */}
        <div className="card lg:col-span-1">
          <div className="card-header">
            <h2 className="text-base font-semibold text-gray-900 dark:text-gray-100 flex items-center gap-2">
              <User size={16} className="text-brand-500" />
              Customer Profile
            </h2>
          </div>
          <div className="card-body space-y-4">
            {profile && (
              <>
                <div className="flex items-center gap-4 pb-4 border-b border-gray-100 dark:border-gray-700/50">
                  <div className="w-14 h-14 rounded-full bg-brand-100 dark:bg-brand-900/50 flex items-center justify-center text-brand-600 dark:text-brand-400 font-bold text-xl">
                    {profile.name?.charAt(0) ?? '?'}
                  </div>
                  <div>
                    <h3 className="text-lg font-bold text-gray-900 dark:text-gray-100">
                      {profile.name}
                    </h3>
                    <span className={`badge ${statusColor(profile.status)}`}>
                      {profile.status}
                    </span>
                  </div>
                </div>

                <InfoRow icon={Mail} label="Email" value={profile.email} />
                <InfoRow icon={Phone} label="Phone" value={profile.phone} />
                <InfoRow icon={Calendar} label="Member Since" value={new Date(profile.created_at).toLocaleDateString()} />
                <InfoRow icon={Shield} label="Tier" value={profile.tier} />
                <InfoRow icon={Building2} label="Company" value={profile.name} />
                {profile.id && <InfoRow icon={MapPin} label="Customer ID" value={profile.id.slice(0, 8) + '...'} />}
              </>
            )}
          </div>
        </div>

        {/* Right Column */}
        <div className="lg:col-span-2 space-y-6">
          {/* Subscription */}
          <div className="card">
            <div className="card-header">
              <h2 className="text-base font-semibold text-gray-900 dark:text-gray-100 flex items-center gap-2">
                <CreditCard size={16} className="text-emerald-500" />
                Subscription
              </h2>
            </div>
            <div className="card-body">
              {subscription ? (
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
                  <div>
                    <p className="metric-label text-xs">Plan</p>
                    <p className="text-sm font-semibold text-gray-900 dark:text-gray-100">
                      {subscription.plan}
                    </p>
                  </div>
                  <div>
                    <p className="metric-label text-xs">Status</p>
                    <span className={`badge ${statusColor(subscription.status)}`}>
                      {subscription.status}
                    </span>
                  </div>
                  <div>
                    <p className="metric-label text-xs">Amount</p>
                    <p className="text-sm font-semibold text-gray-900 dark:text-gray-100">
                      ${subscription.amount.toLocaleString()} / {subscription.currency}
                    </p>
                  </div>
                  <div>
                    <p className="metric-label text-xs">Start Date</p>
                    <p className="text-sm text-gray-700 dark:text-gray-300">
                      {new Date(subscription.start_date).toLocaleDateString()}
                    </p>
                  </div>
                  <div>
                    <p className="metric-label text-xs">End Date</p>
                    <p className="text-sm text-gray-700 dark:text-gray-300">
                      {subscription.end_date
                        ? new Date(subscription.end_date).toLocaleDateString()
                        : '—'}
                    </p>
                  </div>
                  <div>
                    <p className="metric-label text-xs">Auto Renew</p>
                    <span className={`badge ${subscription.auto_renew ? 'badge-success' : 'badge-warning'}`}>
                      {subscription.auto_renew ? 'Enabled' : 'Disabled'}
                    </span>
                  </div>
                </div>
              ) : (
                <p className="text-sm text-gray-400">No subscription data.</p>
              )}
            </div>
          </div>

          {/* Billing History */}
          <div className="card">
            <div className="card-header flex items-center justify-between">
              <h2 className="text-base font-semibold text-gray-900 dark:text-gray-100 flex items-center gap-2">
                <Globe size={16} className="text-violet-500" />
                Billing History
              </h2>
              {refunds.length > 0 && (
                <span className="text-xs text-gray-400 dark:text-gray-500">
                  {refunds.length} refund{refunds.length > 1 ? 's' : ''}
                </span>
              )}
            </div>
            <div className="overflow-x-auto">
              {billing.length === 0 ? (
                <div className="card-body text-center py-8 text-sm text-gray-400">
                  No billing records found.
                </div>
              ) : (
                <table className="w-full">
                  <thead>
                    <tr className="border-b border-gray-100 dark:border-gray-700/50">
                      <th className="table-header">Date</th>
                      <th className="table-header">Description</th>
                      <th className="table-header">Amount</th>
                      <th className="table-header">Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100 dark:divide-gray-700/50">
                    {billing.map((rec) => (
                      <tr key={rec.id} className="hover:bg-gray-50 dark:hover:bg-gray-800/50 transition-colors">
                        <td className="table-cell whitespace-nowrap">
                          {new Date(rec.date).toLocaleDateString()}
                        </td>
                        <td className="table-cell">{rec.description}</td>
                        <td className="table-cell font-medium">
                          ${rec.amount.toLocaleString()}
                        </td>
                        <td className="table-cell">
                          <span className={`badge ${statusColor(rec.status)}`}>
                            {rec.status}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
            {refunds.length > 0 && (
              <div className="border-t border-gray-100 dark:border-gray-700/50">
                <div className="card-body">
                  <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3 flex items-center gap-1.5">
                    <RefreshCw size={14} className="text-amber-500" />
                    Refunds & Credits
                  </h3>
                  <div className="space-y-2">
                    {refunds.map((ref) => (
                      <div key={ref.id} className="flex items-center justify-between text-sm p-2 rounded bg-gray-50 dark:bg-gray-800/50">
                        <div>
                          <span className="text-gray-700 dark:text-gray-300">{ref.reason}</span>
                          <span className="text-xs text-gray-400 ml-2">
                            {new Date(ref.date).toLocaleDateString()}
                          </span>
                        </div>
                        <div className="flex items-center gap-2">
                          <span className="font-medium text-amber-600 dark:text-amber-400">
                            -${ref.amount.toLocaleString()}
                          </span>
                          <span className={`badge ${statusColor(ref.status)}`}>
                            {ref.status}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Tickets */}
          <div className="card">
            <div className="card-header">
              <h2 className="text-base font-semibold text-gray-900 dark:text-gray-100 flex items-center gap-2">
                <TicketCheck size={16} className="text-amber-500" />
                Support Tickets
              </h2>
            </div>
            <div className="overflow-x-auto">
              {tickets.length === 0 ? (
                <div className="card-body text-center py-8 text-sm text-gray-400">
                  No support tickets found.
                </div>
              ) : (
                <table className="w-full">
                  <thead>
                    <tr className="border-b border-gray-100 dark:border-gray-700/50">
                      <th className="table-header">Subject</th>
                      <th className="table-header">Priority</th>
                      <th className="table-header">Status</th>
                      <th className="table-header">Created</th>
                      <th className="table-header">Updated</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100 dark:divide-gray-700/50">
                    {tickets.map((ticket) => (
                      <tr key={ticket.id} className="hover:bg-gray-50 dark:hover:bg-gray-800/50 transition-colors">
                        <td className="table-cell font-medium max-w-[200px] truncate">
                          {ticket.subject}
                        </td>
                        <td className="table-cell">
                          <span
                            className={`badge ${
                              ticket.priority === 'high'
                                ? 'badge-error'
                                : ticket.priority === 'medium'
                                  ? 'badge-warning'
                                  : 'badge-info'
                            }`}
                          >
                            {ticket.priority}
                          </span>
                        </td>
                        <td className="table-cell">
                          <span className={`badge ${statusColor(ticket.status)}`}>
                            {ticket.status.replace('_', ' ')}
                          </span>
                        </td>
                        <td className="table-cell whitespace-nowrap">
                          {new Date(ticket.created_at).toLocaleDateString()}
                        </td>
                        <td className="table-cell whitespace-nowrap">
                          {new Date(ticket.updated_at).toLocaleDateString()}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

// Helper component for profile info rows
function InfoRow({
  icon: Icon,
  label,
  value,
}: {
  icon: any
  label: string
  value: string
}) {
  return (
    <div className="flex items-center gap-3 text-sm">
      <Icon size={16} className="text-gray-400 dark:text-gray-500 flex-shrink-0" />
      <span className="text-gray-500 dark:text-gray-400 min-w-[90px]">{label}</span>
      <span className="text-gray-900 dark:text-gray-100 font-medium truncate">
        {value}
      </span>
    </div>
  )
}

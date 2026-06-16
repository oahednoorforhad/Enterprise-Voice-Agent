import { Link } from '@tanstack/react-router'
import { useQuery } from '@tanstack/react-query'
import {
  Users,
  DollarSign,
  TicketCheck,
  Activity,
  Clock,
  TrendingUp,
  ArrowRight,
  ShieldCheck,
  Headphones,
} from 'lucide-react'
import MetricCard from '../components/MetricCard'
import LoadingSpinner from '../components/LoadingSpinner'
import { api, mock, isMockData } from '../lib/api-client'
import { useAppContext } from './__root'

export function OverviewPage() {
  const { setBackendOffline } = useAppContext()

  // Fetch real data; fall back to mocks on failure
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

  const usageQuery = useQuery({
    queryKey: ['usage', mock.customerId],
    queryFn: () => api.usageAnalytics(mock.customerId),
  })

  // Detect offline
  const anyOffline = [
    profileQuery,
    subscriptionQuery,
    ticketsQuery,
    billingQuery,
    usageQuery,
  ].some((q) => isMockData(q.data as any))

  if (anyOffline) setBackendOffline(true)

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
  const usage = usageQuery.data?.success
    ? (usageQuery.data.data ?? mock.usageData)
    : mock.usageData

  const isLoading =
    profileQuery.isLoading ||
    subscriptionQuery.isLoading ||
    ticketsQuery.isLoading ||
    billingQuery.isLoading ||
    usageQuery.isLoading

  if (isLoading) {
    return <LoadingSpinner fullPage message="Loading dashboard data..." />
  }

  const activeTickets = tickets.filter(
    (t) => t.status === 'open' || t.status === 'in_progress',
  ).length
  const totalRevenue = billing.reduce((sum, b) => sum + b.amount, 0)
  const mrr = subscription?.amount ?? 2999

  return (
    <div className="space-y-8 animate-fade-in">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">
            Welcome back{profile?.name ? `, ${profile.name}` : ''}
          </h1>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
            Here is what is happening with your account today.
          </p>
        </div>
        <Link
          to="/chat"
          className="btn-primary hidden sm:inline-flex"
        >
          <Headphones size={16} />
          Contact Support
        </Link>
      </div>

      {/* Metric Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-4">
        <MetricCard
          title="Active Customers"
          value="1,284"
          description="Across all tiers"
          icon={Users}
          color="brand"
          trend={{ value: 12, positive: true }}
        />
        <MetricCard
          title="Monthly Recurring Revenue"
          value={`$${mrr.toLocaleString()}`}
          description="Current MRR"
          icon={DollarSign}
          color="emerald"
          trend={{ value: 8.3, positive: true }}
        />
        <MetricCard
          title="Open Tickets"
          value={activeTickets}
          description={`${tickets.length} total tickets`}
          icon={TicketCheck}
          color={activeTickets > 0 ? 'amber' : 'emerald'}
          trend={
            activeTickets > 0
              ? { value: activeTickets, positive: false }
              : undefined
          }
        />
        <MetricCard
          title="Avg Response Time"
          value="2.4m"
          description="Last 7 days"
          icon={Clock}
          color="violet"
          trend={{ value: 15, positive: true }}
        />
        <MetricCard
          title="API Calls Today"
          value={usage?.total?.toLocaleString() ?? '8,450'}
          description="Usage analytics"
          icon={Activity}
          color="rose"
          trend={{ value: 5.7, positive: true }}
        />
      </div>

      {/* Quick Actions & Recent Activity */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Quick Actions */}
        <div className="card">
          <div className="card-header">
            <h2 className="text-base font-semibold text-gray-900 dark:text-gray-100">
              Quick Actions
            </h2>
          </div>
          <div className="card-body space-y-2">
            {[
              { label: 'View Customer Dashboard', href: '/dashboard', icon: Users, desc: 'Customer profile, subscription & tickets' },
              { label: 'Search Knowledge Base', href: '/knowledge', icon: ShieldCheck, desc: 'Documentation & policies' },
              { label: 'Explore Analytics', href: '/analytics', icon: TrendingUp, desc: 'Usage metrics & charts' },
              { label: 'Start a Chat Session', href: '/chat', icon: Headphones, desc: 'AI-powered customer support' },
            ].map((action) => (
              <Link
                key={action.href}
                to={action.href}
                className="flex items-center gap-3 p-3 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800/50 transition-colors group"
              >
                <div className="p-2 rounded-lg bg-gray-100 dark:bg-gray-700 text-gray-500 dark:text-gray-400 group-hover:bg-brand-50 group-hover:text-brand-600 dark:group-hover:bg-brand-950/30 dark:group-hover:text-brand-400 transition-colors">
                  <action.icon size={18} />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-gray-900 dark:text-gray-100">
                    {action.label}
                  </p>
                  <p className="text-xs text-gray-400 dark:text-gray-500">
                    {action.desc}
                  </p>
                </div>
                <ArrowRight
                  size={16}
                  className="text-gray-300 dark:text-gray-600 group-hover:text-brand-500 transition-colors"
                />
              </Link>
            ))}
          </div>
        </div>

        {/* Recent Tickets */}
        <div className="card">
          <div className="card-header flex items-center justify-between">
            <h2 className="text-base font-semibold text-gray-900 dark:text-gray-100">
              Recent Tickets
            </h2>
            <Link
              to="/dashboard"
              className="text-xs text-brand-600 dark:text-brand-400 hover:underline"
            >
              View all
            </Link>
          </div>
          <div className="card-body">
            {tickets.length === 0 ? (
              <div className="text-center py-8 text-sm text-gray-400 dark:text-gray-500">
                No tickets found.
              </div>
            ) : (
              <div className="space-y-2">
                {tickets.slice(0, 4).map((ticket) => (
                  <div
                    key={ticket.id}
                    className="flex items-center justify-between p-3 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800/50 transition-colors"
                  >
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-gray-900 dark:text-gray-100 truncate">
                        {ticket.subject}
                      </p>
                      <p className="text-xs text-gray-400 dark:text-gray-500 mt-0.5">
                        {new Date(ticket.created_at).toLocaleDateString()}
                      </p>
                    </div>
                    <span
                      className={`badge ml-3 ${
                        ticket.status === 'open'
                          ? 'badge-warning'
                          : ticket.status === 'in_progress'
                            ? 'badge-info'
                            : 'badge-success'
                      }`}
                    >
                      {ticket.status.replace('_', ' ')}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Plan Summary */}
      {subscription && (
        <div className="card">
          <div className="card-header">
            <h2 className="text-base font-semibold text-gray-900 dark:text-gray-100">
              Subscription Overview
            </h2>
          </div>
          <div className="card-body">
            <div className="flex flex-wrap items-center gap-6">
              <div>
                <p className="metric-label">Plan</p>
                <p className="text-lg font-bold text-gray-900 dark:text-gray-100">
                  {subscription.plan}
                </p>
              </div>
              <div>
                <p className="metric-label">Status</p>
                <span
                  className={`badge ${
                    subscription.status === 'active'
                      ? 'badge-success'
                      : 'badge-warning'
                  }`}
                >
                  {subscription.status}
                </span>
              </div>
              <div>
                <p className="metric-label">Amount</p>
                <p className="text-lg font-bold text-gray-900 dark:text-gray-100">
                  ${subscription.amount.toLocaleString()}/{subscription.currency}
                </p>
              </div>
              <div>
                <p className="metric-label">Auto Renew</p>
                <span
                  className={`badge ${subscription.auto_renew ? 'badge-success' : 'badge-warning'}`}
                >
                  {subscription.auto_renew ? 'Enabled' : 'Disabled'}
                </span>
              </div>
              <div>
                <p className="metric-label">Start Date</p>
                <p className="text-sm font-medium text-gray-700 dark:text-gray-300">
                  {new Date(subscription.start_date).toLocaleDateString()}
                </p>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

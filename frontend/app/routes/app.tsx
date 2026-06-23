import { Outlet } from '@tanstack/react-router'
import { useQuery } from '@tanstack/react-query'
import { api, mock } from '../lib/api-client'
import { useAppContext } from './__root'
import AccountSummary from '../components/AccountSummary'

export function AppShell() {
  const { setBackendOffline } = useAppContext()
  const customerId = mock.customerId

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

  // Detect offline
  if ([profileQuery, subscriptionQuery, ticketsQuery, billingQuery, analyticsQuery].some(
    q => q.isError || (q.data && !q.data.success)
  )) {
    setBackendOffline(true)
  }

  return (
    <div className="flex h-screen overflow-hidden">
      {/* Left panel — chat or voice (rendered by child route) */}
      <div className="flex-1 flex flex-col overflow-hidden">
        <Outlet />
      </div>

      {/* Right panel — always-visible account data */}
      <div className="w-[380px] flex-shrink-0 border-l border-gray-200 dark:border-gray-700 overflow-y-auto">
        <AccountSummary
          profile={profileQuery.data?.data ?? null}
          subscription={subscriptionQuery.data?.data ?? null}
          tickets={ticketsQuery.data?.data ?? null}
          billing={billingQuery.data?.data ?? null}
          analytics={analyticsQuery.data?.data ?? null}
          isLoading={profileQuery.isLoading}
        />
      </div>
    </div>
  )
}

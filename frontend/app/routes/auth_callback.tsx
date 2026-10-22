import { useEffect, useState } from 'react'
import { useNavigate } from '@tanstack/react-router'
import { api, refreshAccessToken, sessionCustomerId } from '../lib/api-client'

export function AuthCallbackPage() {
  const navigate = useNavigate()
  const [status, setStatus] = useState<'saving' | 'fetching' | 'error'>('saving')

  useEffect(() => {
    // The backend set an httpOnly refresh cookie; trade it for an access token
    void refreshAccessToken().then((token) => {
      const customerId = token && sessionCustomerId()
      if (!customerId) {
        setStatus('error')
        return
      }
      setStatus('fetching')
      api.customerProfile(customerId).then((result) => {
        const profile = result.data
        if (profile && !profile.active_scenario) {
          navigate({ to: '/scenarios', replace: true })
        } else {
          navigate({ to: '/app/chat', replace: true })
        }
      }).catch(() => navigate({ to: '/app/chat', replace: true }))
    })
  }, [navigate])

  if (status === 'error') {
    return (
      <div className="flex items-center justify-center min-h-screen bg-surface-white dark:bg-surface-dark">
        <div className="card-flat p-8 max-w-sm text-center">
          <h1 className="font-display text-heading-feature text-ink dark:text-white mb-2">
            Authentication Failed
          </h1>
          <p className="text-caption text-muted-slate mb-4">
            No token was received from the authentication provider.
          </p>
          <a
            href="/"
            className="text-body-small font-medium text-brand-blue hover:underline"
          >
            Back to home
          </a>
        </div>
      </div>
    )
  }

  return (
    <div className="flex items-center justify-center min-h-screen bg-surface-white dark:bg-surface-dark">
      <div className="animate-pulse text-caption text-muted-slate">
        Completing sign-in…
      </div>
    </div>
  )
}

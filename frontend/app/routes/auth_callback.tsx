import { useEffect, useState } from 'react'
import { useNavigate } from '@tanstack/react-router'
import { api } from '../lib/api-client'

export function AuthCallbackPage() {
  const navigate = useNavigate()
  const [status, setStatus] = useState<'saving' | 'fetching' | 'error'>('saving')

  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const token = params.get('token')

    if (!token) {
      setStatus('error')
      return
    }

    try {
      localStorage.setItem('jwt', token)

      // Decode JWT to get customer_id from sub claim
      const payload = JSON.parse(atob(token.split('.')[1]))
      const customerId = payload.sub

      setStatus('fetching')

      api.customerProfile(customerId).then((result) => {
        const profile = result.data
        if (profile && !profile.active_scenario) {
          navigate({ to: '/scenarios', replace: true })
        } else {
          navigate({ to: '/app/chat', replace: true })
        }
      })
    } catch {
      navigate({ to: '/app/chat', replace: true })
    }
  }, [navigate])

  if (status === 'error') {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-50 dark:bg-gray-900">
        <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 p-8 max-w-sm text-center">
          <h1 className="text-lg font-bold text-gray-900 dark:text-gray-100 mb-2">
            Authentication Failed
          </h1>
          <p className="text-sm text-gray-500 dark:text-gray-400 mb-4">
            No token was received from the authentication provider.
          </p>
          <a
            href="/"
            className="text-brand-600 dark:text-brand-400 text-sm font-medium hover:underline"
          >
            Back to home
          </a>
        </div>
      </div>
    )
  }

  return (
    <div className="flex items-center justify-center min-h-screen bg-gray-50 dark:bg-gray-900">
      <div className="animate-pulse text-gray-400 dark:text-gray-500 text-sm">
        Completing sign-in…
      </div>
    </div>
  )
}

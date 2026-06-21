import { useEffect, useState } from 'react'
import { useNavigate } from '@tanstack/react-router'
import { LogIn, Sparkles } from 'lucide-react'

export function LoginPage() {
  const navigate = useNavigate()
  const [checking, setChecking] = useState(true)

  // If already logged in, redirect to home
  useEffect(() => {
    if (localStorage.getItem('jwt')) {
      navigate({ to: '/' })
    } else {
      setChecking(false)
    }
  }, [navigate])

  if (checking) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-50 dark:bg-gray-900">
        <div className="animate-pulse text-gray-400 dark:text-gray-500 text-sm">Loading…</div>
      </div>
    )
  }

  return (
    <div className="flex items-center justify-center min-h-screen bg-gray-50 dark:bg-gray-900 px-4">
      <div className="w-full max-w-sm">
        <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 p-8 text-center">
          {/* Logo */}
          <div className="mx-auto w-12 h-12 rounded-xl bg-brand-600 flex items-center justify-center mb-4">
            <Sparkles size={24} className="text-white" />
          </div>

          <h1 className="text-xl font-bold text-gray-900 dark:text-gray-100 mb-2">
            Enterprise Voice Agent
          </h1>
          <p className="text-sm text-gray-500 dark:text-gray-400 mb-6">
            Sign in to access your enterprise console
          </p>

          <a
            href="http://localhost:8000/api/v1/auth/login/google"
            className="btn-primary w-full inline-flex items-center justify-center gap-2"
          >
            <LogIn size={18} />
            Sign in with Google
          </a>
        </div>
      </div>
    </div>
  )
}

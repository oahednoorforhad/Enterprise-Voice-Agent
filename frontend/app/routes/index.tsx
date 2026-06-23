import { useEffect } from 'react'
import { useNavigate } from '@tanstack/react-router'
import { Sparkles, Zap, Shield, Headphones } from 'lucide-react'

export function LandingPage() {
  const navigate = useNavigate()

  useEffect(() => {
    // If already logged in, redirect to app
    if (localStorage.getItem('jwt')) {
      navigate({ to: '/app/chat', replace: true })
    }
  }, [navigate])

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-900 via-gray-800 to-brand-900 flex flex-col">
      {/* Header */}
      <header className="px-8 py-6 flex items-center gap-3">
        <div className="w-9 h-9 rounded-xl bg-brand-600 flex items-center justify-center">
          <Sparkles size={20} className="text-white" />
        </div>
        <span className="text-white font-bold text-lg">EVA</span>
        <span className="text-gray-400 text-sm ml-1">Enterprise Voice Agent</span>
      </header>

      {/* Hero */}
      <main className="flex-1 flex flex-col items-center justify-center px-8 text-center">
        <div className="max-w-2xl">
          <h1 className="text-5xl font-extrabold text-white leading-tight mb-6">
            Your Enterprise AI<br />
            <span className="text-brand-400">Support Agent</span>
          </h1>
          <p className="text-lg text-gray-300 mb-10 max-w-xl mx-auto">
            EVA handles billing inquiries, technical support, and account management
            through natural voice and chat — 24/7, at enterprise scale.
          </p>

          <a
            href="http://localhost:8000/api/v1/auth/login/google"
            className="inline-flex items-center gap-3 bg-white text-gray-900 font-semibold px-8 py-4 rounded-xl hover:bg-gray-100 transition-colors text-base shadow-lg"
          >
            <svg width="20" height="20" viewBox="0 0 24 24">
              <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
              <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
              <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
              <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
            </svg>
            Sign in with Google
          </a>
        </div>

        {/* Feature highlights */}
        <div className="mt-20 grid grid-cols-1 md:grid-cols-3 gap-8 max-w-3xl w-full text-left">
          {[
            { icon: Headphones, title: 'Voice & Chat', desc: 'Natural language support via voice calls or chat messages' },
            { icon: Zap, title: 'Instant Answers', desc: 'AI resolves billing, tickets, and account queries in seconds' },
            { icon: Shield, title: 'Enterprise Ready', desc: 'Secure, audit-logged, and deployed on your infrastructure' },
          ].map(({ icon: Icon, title, desc }) => (
            <div key={title} className="flex gap-4">
              <div className="w-10 h-10 rounded-lg bg-brand-800/50 flex items-center justify-center flex-shrink-0">
                <Icon size={20} className="text-brand-400" />
              </div>
              <div>
                <h3 className="text-white font-semibold mb-1">{title}</h3>
                <p className="text-gray-400 text-sm">{desc}</p>
              </div>
            </div>
          ))}
        </div>
      </main>
    </div>
  )
}

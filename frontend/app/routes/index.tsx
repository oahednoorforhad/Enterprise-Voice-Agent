import { useEffect } from 'react'
import { useNavigate } from '@tanstack/react-router'
import { Sparkles, Zap, Shield, Headphones } from 'lucide-react'

const API_BASE =
  typeof process !== 'undefined' && process.env?.VITE_API_URL
    ? process.env.VITE_API_URL
    : 'http://localhost:8000'

export function LandingPage() {
  const navigate = useNavigate()

  useEffect(() => {
    if (localStorage.getItem('jwt')) {
      navigate({ to: '/app/chat', replace: true })
    }
  }, [navigate])

  return (
    <div className="min-h-screen bg-surface-white dark:bg-surface-dark flex flex-col">
      {/* Minimal header */}
      <header className="flex items-center gap-3 px-8 py-5 border-b border-hairline dark:border-white/5">
        <div className="w-8 h-8 rounded-sm bg-brand-near flex items-center justify-center">
          <Sparkles size={16} className="text-coral-400" />
        </div>
        <span className="font-display text-heading-feature text-ink dark:text-white">EVA</span>
        <span className="text-caption text-muted-slate ml-1">Enterprise Voice Agent</span>
      </header>

      {/* Hero */}
      <main className="flex-1 flex flex-col items-center justify-center px-8 text-center">
        <div className="max-w-2xl animate-stagger-1">
          <h1 className="heading-hero mb-6">
            Your Enterprise AI<br />
            <span className="text-brand-coral">Support Agent</span>
          </h1>
          <p className="text-body-large text-muted-slate mb-12 max-w-xl mx-auto animate-stagger-2">
            EVA handles billing inquiries, technical support, and account management
            through natural voice and chat — 24/7, at enterprise scale.
          </p>

          <a
            href={`${API_BASE}/api/v1/auth/login/google`}
            className="btn-pill-primary px-8 py-4 text-body font-medium inline-flex items-center gap-3 animate-stagger-3"
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
        <div className="mt-24 grid grid-cols-1 md:grid-cols-3 gap-10 max-w-3xl w-full text-left animate-stagger-4">
          {[
            { icon: Headphones, title: 'Voice & Chat', desc: 'Natural language support via voice calls or chat messages' },
            { icon: Zap, title: 'Instant Answers', desc: 'AI resolves billing, tickets, and account queries in seconds' },
            { icon: Shield, title: 'Enterprise Ready', desc: 'Secure, audit-logged, and deployed on your infrastructure' },
          ].map(({ icon: Icon, title, desc }) => (
            <div key={title} className="flex gap-4">
              <div className="w-10 h-10 rounded-sm bg-surface-stone dark:bg-surface-dark-elevated flex items-center justify-center flex-shrink-0">
                <Icon size={20} className="text-brand-coral" />
              </div>
              <div>
                <h3 className="font-display text-heading-feature text-ink dark:text-white mb-1">{title}</h3>
                <p className="text-caption text-muted-slate">{desc}</p>
              </div>
            </div>
          ))}
        </div>

        {/* Trust strip */}
        <div className="mt-24 mb-16 w-full max-w-3xl animate-stagger-5">
          <p className="label-mono text-center mb-8">Trusted by enterprise teams</p>
          <div className="trust-strip">
            {['ABC', 'Efghi', 'Jklmno', 'Pqrst'].map((name) => (
              <span key={name} className="font-display text-heading-feature text-muted-slate/30 dark:text-gray-600 select-none">
                {name}
              </span>
            ))}
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="border-t border-hairline dark:border-white/5 px-8 py-6">
        <div className="max-w-3xl mx-auto flex flex-col items-center gap-3 text-center">
          {/* Brand */}
          <div className="flex items-center gap-2">
            <Sparkles size={14} className="text-coral-400" />
            <span className="font-display font-semibold text-heading-feature text-ink dark:text-white">
              OahedAI
            </span>
          </div>

          {/* Tagline */}
          <p className="label-mono text-muted-slate dark:text-gray-500">
            Soon to be trusted by many enterprise companies
          </p>

          {/* Divider */}
          <div className="w-16 h-px bg-hairline dark:bg-white/5 my-1" />

          {/* Copyright */}
          <p className="text-caption text-muted-slate/60 dark:text-gray-600">
            © 2026 OahedAI. All rights reserved. &nbsp;·&nbsp; Developed by{' '}
            <span className="font-medium text-muted-slate dark:text-gray-500">OahedAI</span>
          </p>
        </div>
      </footer>
    </div>
  )
}

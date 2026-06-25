import { StrictMode } from 'react'
import ReactDOM from 'react-dom/client'
import { RouterProvider } from '@tanstack/react-router'
import * as Sentry from '@sentry/react'
import { router } from './router'
import './styles/app.css'

const sentryDsn = process.env.VITE_SENTRY_DSN
if (sentryDsn) {
  Sentry.init({
    dsn: sentryDsn,
    environment: process.env.VITE_API_URL?.startsWith('https') ? 'production' : 'development',
    integrations: [
      Sentry.browserTracingIntegration(),
      Sentry.globalHandlersIntegration({ onerror: true, onunhandledrejection: true }),
    ],
    tracesSampleRate: 0.1,
  })
}

const rootEl = document.getElementById('root')
if (!rootEl) throw new Error('Root element #root not found')

ReactDOM.createRoot(rootEl).render(
  <StrictMode>
    <RouterProvider router={router} />
  </StrictMode>,
)

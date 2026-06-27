import { createRouter, createRoute, redirect } from '@tanstack/react-router'
import { Route as rootRoute } from './routes/__root'
import { LandingPage } from './routes/index'
import { AppShell } from './routes/app'
import { AppChatPage } from './routes/app/chat'
import { AppVoicePage } from './routes/app/voice'
import { ScenariosPage } from './routes/scenarios'
import { AuthCallbackPage } from './routes/auth_callback'

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

function requireAuth() {
  if (!localStorage.getItem('jwt')) {
    throw redirect({ to: '/' })
  }
}

// Public routes
const indexRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/',
  component: LandingPage,
})

const authCallbackRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/auth/callback',
  component: AuthCallbackPage,
})

// Auth-required: scenarios
const scenariosRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/scenarios',
  beforeLoad: requireAuth,
  component: ScenariosPage,
})

// Auth-required: app shell (parent)
const appRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/app',
  beforeLoad: requireAuth,
  component: AppShell,
})

// App child routes
const appChatRoute = createRoute({
  getParentRoute: () => appRoute,
  path: '/chat',
  beforeLoad: async () => {
    requireAuth()
    const res = await fetch(`${API_BASE}/api/v1/chat/sessions`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${localStorage.getItem('jwt')}`,
      },
    })
    const body = await res.json()
    const sessionId: string = body.data?.session_id
    throw redirect({ to: '/app/chat/$sessionId', params: { sessionId } })
  },
})

const appChatSessionRoute = createRoute({
  getParentRoute: () => appRoute,
  path: '/chat/$sessionId',
  component: AppChatPage,
})

const appVoiceRoute = createRoute({
  getParentRoute: () => appRoute,
  path: '/voice',
  component: AppVoicePage,
})

const routeTree = rootRoute.addChildren([
  indexRoute,
  authCallbackRoute,
  scenariosRoute,
  appRoute.addChildren([appChatRoute, appChatSessionRoute, appVoiceRoute]),
])

const router = createRouter({ routeTree })

declare module '@tanstack/react-router' {
  interface Register {
    router: typeof router
  }
}

export { router }

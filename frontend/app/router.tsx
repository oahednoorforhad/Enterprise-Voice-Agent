import { createRouter, createRoute, redirect } from '@tanstack/react-router'
import { Route as rootRoute } from './routes/__root'
import { OverviewPage } from './routes/index'
import { ChatPage } from './routes/chat'
import { DashboardPage } from './routes/dashboard'
import { KnowledgePage } from './routes/knowledge'
import { AnalyticsPage } from './routes/analytics'
import { VoicePage } from './routes/voice'
import { LoginPage } from './routes/login'
import { AuthCallbackPage } from './routes/auth_callback'

/** Check whether a valid JWT exists in localStorage. */
function requireAuth() {
  if (!localStorage.getItem('jwt')) {
    throw redirect({ to: '/login' })
  }
}

const indexRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/',
  beforeLoad: requireAuth,
  component: OverviewPage,
})

const chatRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/chat',
  beforeLoad: requireAuth,
  component: ChatPage,
})

const dashboardRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/dashboard',
  beforeLoad: requireAuth,
  component: DashboardPage,
})

const knowledgeRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/knowledge',
  beforeLoad: requireAuth,
  component: KnowledgePage,
})

const analyticsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/analytics',
  beforeLoad: requireAuth,
  component: AnalyticsPage,
})

const voiceRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/voice',
  beforeLoad: requireAuth,
  component: VoicePage,
})

const loginRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/login',
  component: LoginPage,
})

const authCallbackRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/auth/callback',
  component: AuthCallbackPage,
})

const routeTree = rootRoute.addChildren([
  indexRoute,
  chatRoute,
  dashboardRoute,
  knowledgeRoute,
  analyticsRoute,
  voiceRoute,
  loginRoute,
  authCallbackRoute,
])

const router = createRouter({ routeTree })

declare module '@tanstack/react-router' {
  interface Register {
    router: typeof router
  }
}

export { router }

import { createRouter, createRoute } from '@tanstack/react-router'
import { Route as rootRoute } from './routes/__root'
import { OverviewPage } from './routes/index'
import { ChatPage } from './routes/chat'
import { DashboardPage } from './routes/dashboard'
import { KnowledgePage } from './routes/knowledge'
import { AnalyticsPage } from './routes/analytics'

const indexRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/',
  component: OverviewPage,
})

const chatRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/chat',
  component: ChatPage,
})

const dashboardRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/dashboard',
  component: DashboardPage,
})

const knowledgeRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/knowledge',
  component: KnowledgePage,
})

const analyticsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/analytics',
  component: AnalyticsPage,
})

const routeTree = rootRoute.addChildren([
  indexRoute,
  chatRoute,
  dashboardRoute,
  knowledgeRoute,
  analyticsRoute,
])

const router = createRouter({ routeTree })

declare module '@tanstack/react-router' {
  interface Register {
    router: typeof router
  }
}

export { router }

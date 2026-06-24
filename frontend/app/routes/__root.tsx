import { createRootRoute, Outlet, useLocation } from '@tanstack/react-router'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useState, useEffect, createContext, useContext, useCallback } from 'react'
import Sidebar from '../components/Sidebar'

// ---- Context for sharing backend offline state across routes ----------------

interface AppContextType {
  backendOffline: boolean
  setBackendOffline: (v: boolean) => void
  isDark: boolean
  onToggleDark: () => void
}

const AppCtx = createContext<AppContextType>({
  backendOffline: false,
  setBackendOffline: () => {},
  isDark: false,
  onToggleDark: () => {},
})

export const useAppContext = () => useContext(AppCtx)

// ---- Query Client -----------------------------------------------------------

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      staleTime: 30_000,
      refetchOnWindowFocus: false,
    },
  },
})

// ---- Root Route Component ---------------------------------------------------

export const Route = createRootRoute({
  component: RootLayout,
})

function RootLayout() {
  const [isDark, setIsDark] = useState(() => {
    if (typeof document !== 'undefined') {
      return (
        localStorage.getItem('theme') === 'dark' ||
        (!localStorage.getItem('theme') &&
          window.matchMedia('(prefers-color-scheme: dark)').matches)
      )
    }
    return false
  })

  const [backendOffline, setBackendOffline] = useState(false)
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)
  const isLoggedIn = typeof localStorage !== 'undefined' && !!localStorage.getItem('jwt')
  const location = useLocation()
  const hideSidebar = location.pathname === '/' || location.pathname === '/scenarios'

  // Persist dark mode
  useEffect(() => {
    const root = document.documentElement
    if (isDark) {
      root.classList.add('dark')
      localStorage.setItem('theme', 'dark')
    } else {
      root.classList.remove('dark')
      localStorage.setItem('theme', 'light')
    }
  }, [isDark])

  const handleToggleDark = useCallback(() => setIsDark((p) => !p), [])

  // Listen for sidebar collapse changes from Sidebar
  useEffect(() => {
    const handler = (e: CustomEvent) => setSidebarCollapsed(e.detail)
    window.addEventListener('sidebar-collapse' as any, handler as any)
    return () => window.removeEventListener('sidebar-collapse' as any, handler as any)
  }, [])

  return (
    <QueryClientProvider client={queryClient}>
        <AppCtx.Provider value={{ backendOffline, setBackendOffline, isDark, onToggleDark: handleToggleDark }}>
        <div className="flex min-h-dvh bg-surface-white dark:bg-surface-dark">
          {isLoggedIn && !hideSidebar && <Sidebar isDark={isDark} onToggleDark={handleToggleDark} />}
          <main
            className={`flex-1 transition-all duration-300 ${
              isLoggedIn && !hideSidebar
                ? (sidebarCollapsed ? 'md:ml-[68px]' : 'md:ml-[var(--sidebar-width)]')
                : ''
            }`}
          >
            {isLoggedIn && backendOffline && (
              <div className="mx-4 mt-4 mb-2 px-4 py-3 rounded-lg chip-amber flex items-center gap-2 text-body-small">
                <svg
                  width="16"
                  height="16"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  className="flex-shrink-0"
                >
                  <line x1="1" y1="1" x2="23" y2="23" />
                  <path d="M16.72 11.06A10.94 10.94 0 0 1 19 12.55" />
                  <path d="M5 12.55a10.94 10.94 0 0 1 5.17-2.39" />
                  <path d="M10.71 5.05A16 16 0 0 1 22.56 9" />
                  <path d="M1.42 9a15.91 15.91 0 0 1 4.7-2.88" />
                  <path d="M8.53 16.11a6 6 0 0 1 6.95 0" />
                  <line x1="12" y1="20" x2="12.01" y2="20" />
                </svg>
                Backend offline — showing sample data
              </div>
            )}
            <Outlet />
          </main>
        </div>
      </AppCtx.Provider>
    </QueryClientProvider>
  )
}

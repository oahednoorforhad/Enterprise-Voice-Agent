import { useState, useEffect } from 'react'
import { Link, useLocation, useNavigate } from '@tanstack/react-router'
import { useQuery } from '@tanstack/react-query'
import { api } from '../lib/api-client'
import {
  MessageSquare,
  Mic,
  ChevronLeft,
  ChevronRight,
  Sun,
  Moon,
  Menu,
  X,
  Sparkles,
  LogOut,
  Plus,
} from 'lucide-react'

interface SidebarProps {
  isDark: boolean
  onToggleDark: () => void
}

const navItems = [
  { href: '/app/chat', label: 'Chat', icon: MessageSquare },
  { href: '/app/voice', label: 'Voice', icon: Mic },
]

export default function Sidebar({ isDark, onToggleDark }: SidebarProps) {
  const location = useLocation()
  const navigate = useNavigate()

  const { data: sessionData, isLoading, isError, refetch } = useQuery({
    queryKey: ['sessions'],
    queryFn: () => api.listSessions(),
  })

  const currentSessionId = location.pathname.match(/\/app\/chat\/(.+)/)?.[1]
  const currentSession = currentSessionId
    ? sessionData?.data?.sessions?.find(s => s.session_id === currentSessionId)
    : undefined
  const isCurrentSessionEmpty = currentSession?.message_count === 0

  const handleNewConversation = async () => {
    if (creatingSession) return
    setCreatingSession(true)
    try {
      const res = await api.createSession()
      if (res.data?.session_id) {
        navigate({ to: '/app/chat/$sessionId', params: { sessionId: res.data.session_id } })
      }
    } finally {
      setCreatingSession(false)
    }
  }

  const [collapsed, setCollapsed] = useState(false)
  const [mobileOpen, setMobileOpen] = useState(false)
  const [creatingSession, setCreatingSession] = useState(false)

  const handleLogout = () => {
    localStorage.removeItem('jwt')
    localStorage.removeItem('active_scenario_name')
    navigate({ to: '/', replace: true })
  }

  useEffect(() => {
    setMobileOpen(false)
  }, [location.pathname])

  // Dispatch collapse changes so __root can adjust main margin
  useEffect(() => {
    window.dispatchEvent(new CustomEvent('sidebar-collapse', { detail: collapsed }))
  }, [collapsed])

  const sidebarContent = (
    <div className="flex flex-col h-full">
      {/* Near-black brand header */}
      <div className="bg-brand-near dark:bg-black px-5 py-5">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-sm bg-white/10 flex items-center justify-center flex-shrink-0">
            <Sparkles size={16} className="text-coral-400" />
          </div>
          {!collapsed && (
            <div className="min-w-0">
              <h1 className="font-display text-heading-feature text-white truncate leading-none">
                EVA
              </h1>
              <p className="text-micro text-white/50 truncate mt-0.5">
                Enterprise Console
              </p>
            </div>
          )}
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto scrollbar-thin">
        {navItems.map((item) => {
          const isActive = location.pathname === item.href
          return (
            <Link
              key={item.href}
              to={item.href}
              className={`sidebar-link group ${isActive ? 'active' : ''}`}
              title={collapsed ? item.label : undefined}
            >
              <item.icon size={20} className="flex-shrink-0" />
              {!collapsed && <span>{item.label}</span>}
              {isActive && !collapsed && (
                <span className="ml-auto w-1.5 h-1.5 rounded-full bg-ink dark:bg-white" />
              )}
            </Link>
          )
        })}
      </nav>

      {/* Conversations */}
      {!collapsed && (
        <div className="px-3 py-2 border-t border-hairline dark:border-white/5">
          <div className="flex items-center justify-between mb-2">
            <h2 className="text-micro font-semibold uppercase tracking-wider text-muted-slate dark:text-white/40">Conversations</h2>
            <button onClick={handleNewConversation} disabled={creatingSession || isCurrentSessionEmpty} className={`flex items-center gap-1 text-micro text-coral-500 hover:text-coral-400 font-medium transition-colors ${creatingSession || isCurrentSessionEmpty ? 'opacity-50 cursor-not-allowed' : ''}`}>
              <Plus size={14} /> New
            </button>
          </div>
          {isLoading && (
            <div className="space-y-2 py-2">
              {[1,2,3].map(i => <div key={i} className="h-9 bg-surface-stone dark:bg-white/5 animate-pulse rounded-sm" />)}
            </div>
          )}
          {isError && (
            <div className="text-micro text-muted-slate py-2">
              <p>Could not load conversations</p>
              <button onClick={() => refetch()} className="text-coral-500 hover:text-coral-400 mt-1">Retry</button>
            </div>
          )}
          {!isLoading && !isError && sessionData?.data?.sessions?.length === 0 && (
            <p className="text-micro text-muted-slate py-2">No conversations yet</p>
          )}
          {sessionData?.data?.sessions?.map(s => {
            const isActive = location.pathname === `/app/chat/${s.session_id}`
            return (
              <Link key={s.session_id} to="/app/chat/$sessionId" params={{ sessionId: s.session_id }}
                className={`sidebar-link ${isActive ? 'active' : ''}`}>
                <div className="min-w-0 flex-1">
                  <p className="text-body-sm font-medium truncate">{s.title || 'Chat'}</p>
                  <p className="text-micro text-muted-slate truncate">
                    {new Date(s.started_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
                    {s.last_message_preview ? ` — ${s.last_message_preview}` : ''}
                  </p>
                </div>
              </Link>
            )
          })}
        </div>
      )}

      {/* Bottom actions */}
      <div className="px-3 py-4 border-t border-hairline dark:border-white/5 space-y-1">
        <button
          onClick={onToggleDark}
          className="sidebar-link w-full"
          title={collapsed ? (isDark ? 'Light mode' : 'Dark mode') : undefined}
        >
          {isDark ? <Sun size={20} /> : <Moon size={20} />}
          {!collapsed && <span>{isDark ? 'Light mode' : 'Dark mode'}</span>}
        </button>

        <button
          onClick={handleLogout}
          className="sidebar-link w-full"
          title={collapsed ? 'Logout' : undefined}
        >
          <LogOut size={20} />
          {!collapsed && <span>Logout</span>}
        </button>

        <button
          onClick={() => setCollapsed(!collapsed)}
          className="sidebar-link w-full hidden md:flex"
          title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        >
          {collapsed ? <ChevronRight size={20} /> : <ChevronLeft size={20} />}
          {!collapsed && <span>Collapse</span>}
        </button>
      </div>
    </div>
  )

  return (
    <>
      {/* Mobile overlay */}
      {mobileOpen && (
        <div
          className="fixed inset-0 bg-black/40 z-40 md:hidden"
          onClick={() => setMobileOpen(false)}
        />
      )}

      {/* Mobile hamburger — hidden: bottom tab bar handles mobile nav */}
      <button
        className="fixed top-4 left-4 z-50 hidden p-3 min-w-[44px] min-h-[44px] rounded-sm bg-surface-white dark:bg-surface-dark-elevated shadow-sm border border-hairline dark:border-white/10"
        onClick={() => setMobileOpen(true)}
        aria-label="Open menu"
      >
        <Menu size={20} className="text-ink dark:text-gray-100" />
      </button>

      {/* Desktop sidebar */}
      <aside
        className={`hidden md:flex flex-col fixed left-0 top-0 h-full bg-surface-white dark:bg-surface-dark-elevated border-r border-hairline dark:border-white/5 transition-all duration-300 z-30 ${
          collapsed ? 'w-[68px]' : 'w-[var(--sidebar-width)]'
        }`}
      >
        {sidebarContent}
      </aside>

      {/* Mobile sidebar drawer */}
      <aside
        className={`md:hidden fixed inset-y-0 left-0 z-50 w-[280px] bg-surface-white dark:bg-surface-dark-elevated border-r border-hairline dark:border-white/5 transform transition-transform duration-300 ${
          mobileOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
        style={{ paddingTop: 'env(safe-area-inset-top, 0px)' }}
      >
        <div className="flex justify-end p-3">
          <button
            onClick={() => setMobileOpen(false)}
            className="p-2 rounded-sm hover:bg-surface-stone dark:hover:bg-white/5 transition-colors"
            aria-label="Close menu"
          >
            <X size={20} className="text-muted-slate" />
          </button>
        </div>
        {sidebarContent}
      </aside>
    </>
  )
}

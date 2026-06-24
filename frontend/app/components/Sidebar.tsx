import { useState, useEffect } from 'react'
import { Link, useLocation, useNavigate } from '@tanstack/react-router'
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
  const [collapsed, setCollapsed] = useState(false)
  const [mobileOpen, setMobileOpen] = useState(false)

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

import { Outlet, NavLink, useNavigate, useLocation } from 'react-router-dom'
import {
  LayoutDashboard,
  AlertTriangle,
  FileText,
  Shield,
  Car,
  Truck,
  MessageSquare,
  ClipboardCheck,
  GraduationCap,
  FlaskConical,
  BookOpen,
  ListTodo,
  LogOut,
  Menu,
  X,
  Sparkles,
  FolderOpen,
  BarChart3,
  Search,
  Users,
  Calendar,
  Bell,
  Settings,
  Command,
  GitBranch,
  GitMerge,
  Target,
  Award,
  Leaf,
  Bot,
  ChevronDown,
} from 'lucide-react'
import { useState, useEffect, useCallback, lazy, Suspense } from 'react'
import { useTranslation } from 'react-i18next'
import { notificationsApi } from '../api/client'
import OfflineIndicator from './OfflineIndicator'
import { ThemeToggle } from './ui/ThemeToggle'
import { Button } from './ui/Button'
import { cn } from '../helpers/utils'
import { hasRole, isSuperuser } from '../utils/auth'
import { useFeatureFlag } from '../hooks/useFeatureFlag'

/** Deferred until the shell opens Copilot — keeps authenticated first paint lean (S14). */
const AICopilot = lazy(() => import('./copilot/AICopilot'))

interface LayoutProps {
  onLogout: () => void
}

export default function Layout({ onLogout }: LayoutProps) {
  const { t } = useTranslation()
  const canAccessWorkforce = hasRole('admin', 'supervisor')
  const canAccessAdvancedNav = canAccessWorkforce || isSuperuser()
  const canManageUsers = isSuperuser()
  const adminUserManagementEnabled = useFeatureFlag('admin_user_management')

  const hubs = [
    {
      id: 'my-work',
      title: t('nav.my_work'),
      icon: ListTodo,
      items: [
        { path: '/actions', icon: ListTodo, label: t('nav.actions') },
        { path: '/workflows', icon: GitBranch, label: t('nav.workflow_center') },
      ],
    },
    {
      id: 'safety-cases',
      title: t('nav.safety_cases'),
      icon: AlertTriangle,
      items: [
        { path: '/incidents', icon: AlertTriangle, label: t('nav.incidents') },
        { path: '/near-misses', icon: AlertTriangle, label: t('nav.near_misses') },
        { path: '/rtas', icon: Car, label: t('nav.rtas') },
        { path: '/complaints', icon: MessageSquare, label: t('nav.complaints') },
        { path: '/investigations', icon: FlaskConical, label: t('nav.investigations') },
        { path: '/vehicle-checklists', icon: Truck, label: t('nav.vehicle_checklists') },
      ],
    },
    ...(canAccessWorkforce
      ? [
          {
            id: 'workforce',
            title: t('nav.workforce'),
            icon: Users,
            items: [
              {
                path: '/workforce/dashboard',
                icon: BarChart3,
                label: t('nav.competency'),
              },
              {
                path: '/workforce/assessments',
                icon: ClipboardCheck,
                label: t('nav.assessments'),
              },
              {
                path: '/workforce/training',
                icon: GraduationCap,
                label: t('nav.training'),
              },
              { path: '/workforce/engineers', icon: Users, label: t('nav.engineers') },
              { path: '/workforce/calendar', icon: Calendar, label: t('nav.calendar') },
            ],
          },
        ]
      : []),
    {
      id: 'assurance',
      title: t('nav.assurance'),
      icon: ClipboardCheck,
      items: [
        { path: '/audits', icon: ClipboardCheck, label: t('nav.audits') },
        { path: '/audit-templates', icon: Sparkles, label: t('nav.audit_builder') },
        { path: '/uvdb', icon: Award, label: t('nav.uvdb_achilles') },
        { path: '/planet-mark', icon: Leaf, label: t('nav.planet_mark') },
        { path: '/customer-audits', icon: Users, label: t('nav.customer_audits') },
      ],
    },
    {
      id: 'compliance-sustainability',
      title: t('nav.compliance_sustainability'),
      icon: Shield,
      items: [
        { path: '/ims', icon: GitMerge, label: t('nav.overview') },
        { path: '/standards', icon: BookOpen, label: t('nav.standards') },
        { path: '/compliance', icon: Shield, label: t('nav.iso_compliance') },
        ...(canAccessAdvancedNav
          ? [
              {
                path: '/compliance-automation',
                icon: Shield,
                label: t('nav.compliance_automation'),
              },
            ]
          : []),
      ],
    },
    {
      id: 'risk-improvement',
      title: t('nav.risk_improvement'),
      icon: Target,
      items: [{ path: '/risk-register', icon: Target, label: t('nav.risk_register') }],
    },
    {
      id: 'library',
      title: t('nav.library'),
      icon: FolderOpen,
      items: [
        { path: '/documents', icon: FolderOpen, label: t('nav.documents') },
        { path: '/policies', icon: FileText, label: t('nav.policies') },
      ],
    },
    ...(canManageUsers && adminUserManagementEnabled
      ? [
          {
            id: 'admin',
            title: t('nav.admin'),
            icon: Settings,
            items: [{ path: '/admin/users', icon: Users, label: t('nav.user_management') }],
          },
        ]
      : []),
  ]

  const location = useLocation()
  const pathIsActive = (path: string) =>
    location.pathname === path || location.pathname.startsWith(`${path}/`)
  const activeHubId = hubs.find((hub) => hub.items.some((item) => pathIsActive(item.path)))?.id
  const [expandedHubs, setExpandedHubs] = useState<Record<string, boolean>>(() =>
    Object.fromEntries(
      hubs.map((hub) => [hub.id, hub.items.some((item) => pathIsActive(item.path))]),
    ),
  )

  useEffect(() => {
    if (activeHubId) {
      setExpandedHubs((current) =>
        current[activeHubId] ? current : { ...current, [activeHubId]: true },
      )
    }
  }, [activeHubId])

  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [unreadNotifications, setUnreadNotifications] = useState(0)
  const [copilotOpen, setCopilotOpen] = useState(false)
  const navigate = useNavigate()

  const fetchUnreadCount = useCallback(() => {
    notificationsApi
      .getUnreadCount()
      .then((res) => setUnreadNotifications(res.data?.unread_count ?? 0))
      .catch(() => {})
  }, [])

  useEffect(() => {
    fetchUnreadCount()
    const handle = setInterval(fetchUnreadCount, 60_000)
    return () => clearInterval(handle)
  }, [fetchUnreadCount])

  // Keyboard shortcut for global search (Cmd+K or Ctrl+K)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault()
        navigate('/search')
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [navigate])

  return (
    <div className="min-h-screen bg-background safe-area-top">
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:absolute focus:z-50 focus:top-2 focus:left-2 focus:px-4 focus:py-2 focus:bg-primary focus:text-primary-foreground focus:rounded-md focus:outline-none"
      >
        {t('a11y.skip_to_content', 'Skip to main content')}
      </a>
      {/* Top Bar */}
      <header className="fixed top-0 right-0 left-0 lg:left-72 h-16 bg-card/95 backdrop-blur-lg border-b border-border z-30 flex items-center justify-between px-4 sm:px-6">
        {/* Search Bar */}
        <button
          onClick={() => navigate('/search')}
          className={cn(
            'flex items-center gap-3 px-4 py-2 rounded-lg text-muted-foreground',
            'bg-surface border border-border',
            'hover:text-foreground hover:border-border-strong transition-all',
            'w-full max-w-md',
          )}
        >
          <Search className="w-4 h-4" />
          <span className="text-sm">{t('search')}...</span>
          <div className="ml-auto flex items-center gap-1 text-xs text-muted-foreground">
            <Command className="w-3 h-3" />
            <span>K</span>
          </div>
        </button>

        {/* Right Actions */}
        <div className="flex items-center gap-2">
          <ThemeToggle />

          <NavLink
            to="/notifications"
            className={cn(
              'relative p-2 rounded-lg transition-colors',
              'text-muted-foreground hover:text-foreground hover:bg-surface',
            )}
          >
            <Bell className="w-5 h-5" />
            {unreadNotifications > 0 && (
              <span className="absolute -top-0.5 -right-0.5 w-4 h-4 bg-destructive text-destructive-foreground text-[10px] font-bold rounded-full flex items-center justify-center">
                {unreadNotifications}
              </span>
            )}
          </NavLink>

          <NavLink
            to={canManageUsers && adminUserManagementEnabled ? '/admin/users' : '/dashboard'}
            className="p-2 text-muted-foreground hover:text-foreground hover:bg-surface rounded-lg transition-colors"
          >
            <Settings className="w-5 h-5" />
          </NavLink>

          {/* AI Copilot Toggle */}
          <Button
            onClick={() => setCopilotOpen(!copilotOpen)}
            variant={copilotOpen ? 'default' : 'ghost'}
            size="sm"
            className={cn('gap-2', copilotOpen && 'shadow-glow')}
          >
            <Bot className="w-4 h-4" />
            <span className="hidden sm:inline">{t('nav.copilot')}</span>
          </Button>
        </div>
      </header>

      {/* Mobile menu button */}
      <button
        onClick={() => setSidebarOpen(!sidebarOpen)}
        className="lg:hidden fixed top-4 left-4 z-50 p-2 rounded-lg bg-card border border-border text-foreground shadow-sm"
      >
        {sidebarOpen ? <X size={24} /> : <Menu size={24} />}
      </button>

      {/* Sidebar */}
      <aside
        className={cn(
          'fixed inset-y-0 left-0 z-40 w-72 bg-card/95 backdrop-blur-xl border-r border-border',
          'transform transition-transform duration-300 ease-in-out',
          'lg:translate-x-0',
          sidebarOpen ? 'translate-x-0' : '-translate-x-full',
        )}
      >
        <div className="flex flex-col h-full">
          {/* Logo */}
          <div className="p-6 border-b border-border">
            <div className="flex items-center gap-3">
              <div className="w-11 h-11 rounded-xl gradient-brand flex items-center justify-center shadow-glow">
                <Shield className="w-6 h-6 text-primary-foreground" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h1 className="text-lg font-bold text-foreground">QGP</h1>
                  <span className="px-1.5 py-0.5 text-[10px] font-bold gradient-brand text-primary-foreground rounded-full flex items-center gap-0.5">
                    <Sparkles className="w-2.5 h-2.5" />
                    PRO
                  </span>
                </div>
                <p className="text-xs text-muted-foreground">{t('login.title')}</p>
              </div>
            </div>
          </div>

          {/* Navigation */}
          <nav className="flex-1 p-4 overflow-y-auto">
            <div className="space-y-1">
              <NavLink
                to="/dashboard"
                onClick={() => setSidebarOpen(false)}
                className={({ isActive }) =>
                  cn(
                    'flex items-center gap-3 px-4 py-2.5 rounded-xl text-sm font-medium',
                    'transition-all duration-200 group',
                    isActive
                      ? 'bg-primary/10 text-primary border border-primary/20'
                      : 'text-muted-foreground hover:text-foreground hover:bg-surface',
                  )
                }
              >
                {({ isActive }) => (
                  <>
                    <LayoutDashboard
                      className={cn(
                        'w-5 h-5 transition-colors',
                        isActive
                          ? 'text-primary'
                          : 'text-muted-foreground group-hover:text-foreground',
                      )}
                    />
                    {t('nav.home')}
                    {isActive && <div className="ml-auto w-1.5 h-1.5 rounded-full bg-primary" />}
                  </>
                )}
              </NavLink>

              {hubs.map((hub) => {
                const expanded = expandedHubs[hub.id] ?? false
                const active = hub.items.some((item) => pathIsActive(item.path))

                return (
                  <div key={hub.id}>
                    <button
                      type="button"
                      onClick={() =>
                        setExpandedHubs((current) => ({
                          ...current,
                          [hub.id]: !expanded,
                        }))
                      }
                      aria-expanded={expanded}
                      aria-controls={`nav-hub-${hub.id}`}
                      className={cn(
                        'flex w-full items-center gap-3 px-4 py-2.5 rounded-xl text-sm font-medium',
                        'transition-all duration-200 group',
                        active
                          ? 'bg-primary/10 text-primary'
                          : 'text-muted-foreground hover:text-foreground hover:bg-surface',
                      )}
                    >
                      <hub.icon
                        className={cn(
                          'w-5 h-5 transition-colors',
                          active
                            ? 'text-primary'
                            : 'text-muted-foreground group-hover:text-foreground',
                        )}
                      />
                      <span>{hub.title}</span>
                      <ChevronDown
                        className={cn(
                          'ml-auto w-4 h-4 transition-transform',
                          expanded ? 'rotate-0' : '-rotate-90',
                        )}
                      />
                    </button>

                    {expanded && (
                      <div id={`nav-hub-${hub.id}`} className="mt-1 ml-4 space-y-1">
                        {hub.items.map((item) => (
                          <NavLink
                            key={item.path}
                            to={item.path}
                            onClick={() => setSidebarOpen(false)}
                            className={({ isActive }) =>
                              cn(
                                'flex items-center gap-3 px-4 py-2 rounded-xl text-sm font-medium',
                                'transition-all duration-200 group',
                                isActive
                                  ? 'bg-primary/10 text-primary border border-primary/20'
                                  : 'text-muted-foreground hover:text-foreground hover:bg-surface',
                              )
                            }
                          >
                            {({ isActive }) => (
                              <>
                                <item.icon
                                  className={cn(
                                    'w-4 h-4 transition-colors',
                                    isActive
                                      ? 'text-primary'
                                      : 'text-muted-foreground group-hover:text-foreground',
                                  )}
                                />
                                {item.label}
                                {isActive && (
                                  <div className="ml-auto w-1.5 h-1.5 rounded-full bg-primary" />
                                )}
                              </>
                            )}
                          </NavLink>
                        ))}
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          </nav>

          {/* Footer */}
          <div className="p-4 border-t border-border">
            <button
              onClick={onLogout}
              className={cn(
                'flex items-center gap-3 px-4 py-3 w-full rounded-xl text-sm font-medium',
                'text-muted-foreground hover:text-destructive hover:bg-destructive/10 transition-all duration-200',
              )}
            >
              <LogOut size={20} />
              {t('logout')}
            </button>
          </div>
        </div>
      </aside>

      {/* Main content */}
      <main id="main-content" className="lg:pl-72 pt-16">
        <div className="p-4 sm:p-6 lg:p-8 min-h-screen">
          <Outlet />
        </div>
      </main>

      {/* Mobile overlay */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-30 lg:hidden"
          onClick={() => setSidebarOpen(false)}
          aria-hidden="true"
        />
      )}

      {/* AI Copilot — code-split; mount only when opened */}
      {copilotOpen ? (
        <Suspense fallback={null}>
          <AICopilot
            isOpen={copilotOpen}
            onClose={() => setCopilotOpen(false)}
            currentPage={window.location.pathname}
          />
        </Suspense>
      ) : null}

      {/* Offline status indicator */}
      <OfflineIndicator />
    </div>
  )
}

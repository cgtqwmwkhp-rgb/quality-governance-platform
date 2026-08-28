import { Outlet, NavLink, useLocation } from 'react-router-dom'
import {
  LayoutDashboard,
  AlertTriangle,
  Shield,
  Car,
  Truck,
  MessageSquare,
  ClipboardCheck,
  ClipboardList,
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
  Bot,
  ChevronDown,
  FileText,
  Download,
  Package,
  Webhook,
  PanelLeftClose,
  PanelLeft,
} from 'lucide-react'
import { BrandMarkTile } from './BrandMark'
import { useState, useEffect, useCallback, useRef, lazy, Suspense, Fragment } from 'react'
import type { HTMLAttributes } from 'react'
import { useTranslation } from 'react-i18next'
import { notificationsApi } from '../api/client'
import { safetyAssetsApi } from '../api/safetyAssetsClient'
import OfflineIndicator from './OfflineIndicator'
import KeyboardShortcutHelp from './KeyboardShortcutHelp'
import { ThemeToggle } from './ui/ThemeToggle'
import { Button } from './ui/Button'
import { IconButton, iconOnlyControlProps } from './ui/IconButton'
import { cn } from '../helpers/utils'
import { hasRole, isSuperuser } from '../utils/auth'
import { useFeatureFlag } from '../hooks/useFeatureFlag'
import { isAICopilotDemoEnabled } from '../config/aiCopilotDemo'
import { isAIIntelligenceRouteEnabled } from '../config/aiIntelligenceRoute'
import { CUSTOMER_AUDITS_PROGRAMME_PATH, navItemIsActive } from './assuranceHubHelpers'
import { usePreferencesStore } from '../stores/usePreferencesStore'

/** Deferred until the shell opens PlantEx Assist — keeps authenticated first paint lean (S14). */
const AICopilot = lazy(() => import('./copilot/AICopilot'))
const GlobalSearchPalette = lazy(() => import('./search/GlobalSearchPalette'))
/** Only ever rendered in the last two minutes of a session — keep it off the shell's critical path. */
const SessionExpiryWarning = lazy(() => import('./SessionExpiryWarning'))

interface LayoutProps {
  onLogout: () => void
  /**
   * Session countdown state from `useSessionKeepalive`, owned by App so the
   * keepalive scheduler stays a singleton. Optional so tests and any future
   * caller can mount the shell without it (PX-179).
   */
  sessionExpiryImminent?: boolean
  sessionExtending?: boolean
  onExtendSession?: () => void
}

/** Referenced by the mobile menu button's aria-controls. */
const SIDEBAR_ID = 'app-sidebar'

/** Tailwind's `lg` breakpoint — above this the sidebar is permanent, not a drawer. */
const DESKTOP_MEDIA_QUERY = '(min-width: 1024px)'

/**
 * React 18 does not accept `inert` as a boolean JSX prop, so it has to be
 * spread as an empty-string attribute. `aria-hidden` alone removes the
 * background from the accessibility tree; `inert` additionally stops focus and
 * pointer events reaching it in browsers that support it (PX-162).
 */
const INERT_PROPS = { inert: '' } as unknown as HTMLAttributes<HTMLElement>

export default function Layout({
  onLogout,
  sessionExpiryImminent = false,
  sessionExtending = false,
  onExtendSession,
}: LayoutProps) {
  const { t } = useTranslation()
  const sidebarCollapsed = usePreferencesStore((state) => state.sidebarCollapsed)
  const toggleSidebar = usePreferencesStore((state) => state.toggleSidebar)
  const [searchOpen, setSearchOpen] = useState(false)
  const [isDesktop, setIsDesktop] = useState(false)
  const canAccessWorkforce = hasRole('admin', 'supervisor')
  const canAccessAdvancedNav = canAccessWorkforce || isSuperuser()
  // Match App.tsx `/admin` RequireRole — hub must be discoverable to roles that
  // can already deep-link the Admin Console (not only isSuperuser + flag).
  const canAccessAdmin = hasRole('admin', 'manager', 'hsec')
  const complianceScheduleEnabled = useFeatureFlag('compliance_schedule')
  const jobLifecycleEnabled = useFeatureFlag('job_lifecycle')
  const registerCatalogueEnabled = useFeatureFlag('register_catalogue')
  const canAccessComplianceSchedule = complianceScheduleEnabled && canAccessAdvancedNav

  // Optional `group` nests siblings under a non-hub section label inside a hub.
  // Fleet & Assets is a first-level hub (FR-NAV-FLEET-01) — not a Safety subsection.
  type NavHubItem = {
    path: string
    icon: typeof ListTodo
    label: string
    group?: string
  }

  const hubs: Array<{
    id: string
    title: string
    icon: typeof ListTodo
    items: NavHubItem[]
  }> = [
    {
      id: 'my-work',
      title: t('nav.my_work'),
      icon: ListTodo,
      items: [
        { path: '/actions', icon: ListTodo, label: t('nav.actions') },
        { path: '/my-reading', icon: BookOpen, label: t('nav.my_reading', { defaultValue: 'My Reading' }) },
        {
          path: '/my-compliance',
          icon: Award,
          label: t('nav.my_compliance_passport', { defaultValue: 'Compliance Passport' }),
        },
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
        { path: '/complaints', icon: MessageSquare, label: t('nav.complaints', 'Feedback') },
        { path: '/investigations', icon: FlaskConical, label: t('nav.investigations') },
      ],
    },
    {
      id: 'fleet-assets',
      title: t('nav.fleet_assets', { defaultValue: 'Fleet & Assets' }),
      icon: Truck,
      items: [
        {
          path: '/vehicle-checklists',
          icon: Truck,
          label: t('nav.vehicle_checklists'),
        },
        {
          path: '/safety-assets',
          icon: Package,
          label: t('nav.safety_asset_register', { defaultValue: 'Asset Register' }),
        },
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
            ],
          },
        ]
      : []),
    {
      id: 'assurance',
      title: t('nav.audits_hub', { defaultValue: 'Audits' }),
      icon: ClipboardCheck,
      // N-NAV: Audits is the engagement work queue. Customer & external is
      // work, not a scheme. UVDB / Planet Mark enter from Standards.
      items: [
        { path: '/audits', icon: ClipboardCheck, label: t('nav.audits') },
        { path: '/audit-templates', icon: Sparkles, label: t('nav.audit_builder') },
        {
          path: CUSTOMER_AUDITS_PROGRAMME_PATH,
          icon: Users,
          label: t('nav.customer_external', { defaultValue: 'Customer & external' }),
        },
      ],
    },
    {
      id: 'compliance-sustainability',
      title: t('nav.compliance_sustainability'),
      icon: Shield,
      items: [
        { path: '/ims', icon: GitMerge, label: t('nav.overview') },
        { path: '/compliance', icon: BookOpen, label: t('nav.standards') },
        {
          path: '/knowledge-exceptions',
          icon: Sparkles,
          label: t('nav.knowledge_exceptions', { defaultValue: 'AI Exceptions' }),
        },
        ...(canAccessComplianceSchedule
          ? [
              {
                path: '/compliance-schedule',
                icon: Calendar,
                label: t('nav.compliance_schedule', { defaultValue: 'Compliance Schedule' }),
              },
            ]
          : []),
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
      items: [
        { path: '/risk-register', icon: Target, label: t('nav.risk_register') },
        ...(jobLifecycleEnabled
          ? [
              {
                path: '/job-lifecycle',
                icon: GitBranch,
                label: t('nav.job_lifecycle', { defaultValue: 'Job cycle' }),
              },
            ]
          : []),
      ],
    },
    {
      id: 'library',
      title: t('nav.library'),
      icon: FolderOpen,
      items: [
        {
          path: '/documents',
          icon: FolderOpen,
          label: t('nav.documents', { defaultValue: 'Documents' }),
        },
        ...(registerCatalogueEnabled
          ? [
              {
                path: '/registers',
                icon: ClipboardList,
                label: t('nav.registers', { defaultValue: 'Registers' }),
              },
            ]
          : []),
        {
          path: '/document-control',
          icon: FileText,
          label: t('nav.document_control', { defaultValue: 'Document Control' }),
        },
      ],
    },
    {
      id: 'insights',
      title: t('nav.insights', { defaultValue: 'Insights' }),
      icon: BarChart3,
      items: [
        { path: '/analytics', icon: BarChart3, label: t('nav.analytics') },
        { path: '/analytics/hs-performance', icon: BarChart3, label: 'H&S Performance' },
        {
          path: '/analytics/safety-insights',
          icon: Bot,
          label: t('nav.safety_insights', { defaultValue: 'Safety Insights' }),
        },
        { path: '/calendar', icon: Calendar, label: t('nav.calendar') },
        { path: '/exports', icon: Download, label: t('nav.export_center') },
        ...(isAIIntelligenceRouteEnabled()
          ? [{ path: '/ai-intelligence', icon: Bot, label: t('nav.ai_intelligence') }]
          : []),
      ],
    },
    ...(canAccessAdmin
      ? [
          {
            id: 'admin',
            title: t('nav.admin'),
            icon: Settings,
            items: [
              {
                path: '/admin',
                icon: LayoutDashboard,
                label: t('nav.admin_console', { defaultValue: 'Admin Console' }),
              },
              { path: '/admin/users', icon: Users, label: t('nav.user_management') },
              { path: '/audit-trail', icon: ClipboardList, label: t('nav.audit_trail') },
              {
                path: '/admin/forms',
                icon: FileText,
                label: t('nav.forms', { defaultValue: 'Forms' }),
              },
              { path: '/admin/settings', icon: Settings, label: t('nav.settings') },
              {
                path: '/admin/notifications',
                icon: Bell,
                label: t('nav.notifications', { defaultValue: 'Notifications' }),
              },
              {
                path: '/admin/hseq-inbox',
                icon: MessageSquare,
                label: t('nav.hsec_inbox', { defaultValue: 'HSEQ Inbox' }),
              },
              {
                path: '/admin/partner-webhooks',
                icon: Webhook,
                label: t('nav.partner_webhooks', { defaultValue: 'Partner Webhooks' }),
              },
              {
                path: '/admin/lookups',
                icon: ClipboardCheck,
                label: t('nav.lookups', { defaultValue: 'Lookups' }),
              },
              {
                path: '/admin/hs-reporting-hours',
                icon: BarChart3,
                label: t('nav.hs_reporting_hours', { defaultValue: 'H&S reporting hours' }),
              },
            ],
          },
        ]
      : []),
  ]

  const location = useLocation()
  const pathIsActive = (path: string) =>
    navItemIsActive(path, location.pathname, location.search)
  // Library shell owns Documents / Policies / Document campaigns tabs.
  // Those are not extra sidebar items, but they still belong to the Library hub.
  const libraryShellActive = pathIsActive('/documents') || pathIsActive('/policies')
  const hubIsActive = (hub: (typeof hubs)[number]) =>
    hub.items.some((item) => pathIsActive(item.path)) ||
    (hub.id === 'library' && libraryShellActive)
  const activeHubId = hubs.find((hub) => hubIsActive(hub))?.id
  const [expandedHubs, setExpandedHubs] = useState<Record<string, boolean>>(() =>
    Object.fromEntries(hubs.map((hub) => [hub.id, hubIsActive(hub)])),
  )

  useEffect(() => {
    if (activeHubId) {
      setExpandedHubs((current) =>
        current[activeHubId] ? current : { ...current, [activeHubId]: true },
      )
    }
  }, [activeHubId])

  const [sidebarOpen, setSidebarOpen] = useState(false)
  const menuButtonRef = useRef<HTMLButtonElement>(null)
  const sidebarRef = useRef<HTMLElement>(null)

  // Above `lg` the sidebar is permanent chrome, not a drawer. Force it closed
  // so a stale `sidebarOpen` left over from a narrow viewport (rotation, window
  // resize) can never mark the desktop page inert.
  useEffect(() => {
    const mql = window.matchMedia(DESKTOP_MEDIA_QUERY)
    const sync = () => {
      setIsDesktop(mql.matches)
      if (mql.matches) setSidebarOpen(false)
    }
    sync()
    mql.addEventListener('change', sync)
    return () => mql.removeEventListener('change', sync)
  }, [])

  // The open drawer is a modal: Escape dismisses it and focus moves inside so
  // a keyboard or screen-reader user is not left behind the dimmed overlay
  // (PX-162).
  useEffect(() => {
    if (!sidebarOpen) return

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setSidebarOpen(false)
      }
    }
    document.addEventListener('keydown', onKeyDown)

    // Captured now rather than in cleanup: the menu button renders on every
    // pass, so this is the same node either way, and reading a ref during
    // teardown is the pattern react-hooks warns about.
    const previouslyFocused = document.activeElement as HTMLElement | null
    const restoreFocusTo = menuButtonRef.current ?? previouslyFocused
    sidebarRef.current?.focus()

    return () => {
      document.removeEventListener('keydown', onKeyDown)
      // Hand focus back to the control that opened the drawer so keyboard
      // users are not dumped at the top of the document.
      restoreFocusTo?.focus()
    }
  }, [sidebarOpen])
  const [unreadNotifications, setUnreadNotifications] = useState(0)
  const [pendingSafetyLookups, setPendingSafetyLookups] = useState(0)
  const [copilotOpen, setCopilotOpen] = useState(false)
  const copilotDemoEnabled = isAICopilotDemoEnabled()

  const fetchUnreadCount = useCallback(() => {
    notificationsApi
      .getUnreadCount()
      .then((res) => setUnreadNotifications(res.data?.unread_count ?? 0))
      .catch(() => {})
  }, [])

  const fetchPendingSafetyLookups = useCallback(() => {
    if (!canAccessAdmin) {
      setPendingSafetyLookups(0)
      return
    }
    safetyAssetsApi
      .listPendingSafetyLookups()
      .then((res) => setPendingSafetyLookups(res.data?.total ?? res.data?.items?.length ?? 0))
      .catch(() => {
        // Fail closed — clear stale badge rather than leave an outdated count.
        setPendingSafetyLookups(0)
      })
  }, [canAccessAdmin])

  useEffect(() => {
    fetchUnreadCount()
    fetchPendingSafetyLookups()
    const handle = setInterval(() => {
      fetchUnreadCount()
      fetchPendingSafetyLookups()
    }, 60_000)
    return () => clearInterval(handle)
  }, [fetchUnreadCount, fetchPendingSafetyLookups])

  // Refresh pending badge when navigating Admin/Lookups (e.g. after approvals).
  useEffect(() => {
    if (
      location.pathname.startsWith('/admin') ||
      location.pathname.startsWith('/safety-assets')
    ) {
      fetchPendingSafetyLookups()
    }
  }, [location.pathname, location.search, fetchPendingSafetyLookups])

  // Keyboard shortcut for global search palette (Cmd+K or Ctrl+K)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault()
        setSearchOpen(true)
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [])

  return (
    <div className="min-h-screen bg-background safe-area-top">
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:absolute focus:z-50 focus:top-2 focus:left-2 focus:px-4 focus:py-2 focus:bg-primary focus:text-primary-foreground focus:rounded-md focus:outline-none"
      >
        {t('a11y.skip_to_content', 'Skip to main content')}
      </a>
      <Suspense fallback={null}>
        <GlobalSearchPalette open={searchOpen} onOpenChange={setSearchOpen} />
      </Suspense>
      {/* Top Bar */}
      <header
        aria-hidden={sidebarOpen || undefined}
        {...(sidebarOpen ? INERT_PROPS : {})}
        className={cn(
          'fixed top-0 right-0 left-0 h-16 bg-card/95 backdrop-blur-lg border-b border-border z-30 flex items-center justify-between px-4 sm:px-6',
          sidebarCollapsed ? 'lg:left-16' : 'lg:left-72',
        )}
      >
        {/* Search Bar — opens overlay palette; does not navigate away */}
        <button
          type="button"
          onClick={() => setSearchOpen(true)}
          aria-label={t('search.open_palette', 'Open search')}
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
            {...iconOnlyControlProps(
              unreadNotifications > 0
                ? t('a11y.notifications_unread', { count: unreadNotifications })
                : t('nav.notifications'),
            )}
            className={cn(
              'relative p-2 rounded-lg transition-colors',
              'text-muted-foreground hover:text-foreground hover:bg-surface',
            )}
          >
            <Bell className="w-5 h-5" aria-hidden="true" />
            {unreadNotifications > 0 && (
              <span
                aria-hidden="true"
                className="absolute -top-0.5 -right-0.5 w-4 h-4 bg-destructive text-destructive-foreground text-[10px] font-bold rounded-full flex items-center justify-center"
              >
                {unreadNotifications}
              </span>
            )}
          </NavLink>

          <NavLink
            to={canAccessAdmin ? '/admin' : '/dashboard'}
            className="p-2 text-muted-foreground hover:text-foreground hover:bg-surface rounded-lg transition-colors"
            {...iconOnlyControlProps(t('nav.settings'))}
          >
            <Settings className="w-5 h-5" aria-hidden="true" />
          </NavLink>

          {/* PlantEx Assist toggle — hidden unless demo/surface flag enabled (PX-248) */}
          {copilotDemoEnabled && (
            <Button
              onClick={() => setCopilotOpen(!copilotOpen)}
              variant={copilotOpen ? 'default' : 'ghost'}
              size="sm"
              className={cn('gap-2', copilotOpen && 'shadow-glow')}
              aria-label={t('nav.copilot')}
            >
              <Bot className="w-4 h-4" />
              <span className="hidden sm:inline">{t('nav.copilot')}</span>
            </Button>
          )}
        </div>
      </header>

      {/* Mobile menu button */}
      <IconButton
        ref={menuButtonRef}
        label={sidebarOpen ? t('a11y.close_menu') : t('a11y.open_menu')}
        aria-expanded={sidebarOpen}
        aria-controls={SIDEBAR_ID}
        onClick={() => setSidebarOpen(!sidebarOpen)}
        className="lg:hidden fixed top-4 left-4 z-50 h-auto w-auto p-2 rounded-lg bg-card border border-border text-foreground shadow-sm"
      >
        {sidebarOpen ? <X size={24} aria-hidden="true" /> : <Menu size={24} aria-hidden="true" />}
      </IconButton>

      {/* Sidebar */}
      <aside
        id={SIDEBAR_ID}
        ref={sidebarRef}
        data-collapsed={sidebarCollapsed ? 'true' : undefined}
        // Only a dialog while it is the mobile drawer. On desktop it is
        // permanent navigation and must stay an ordinary complementary region.
        role={sidebarOpen ? 'dialog' : undefined}
        aria-modal={sidebarOpen ? true : undefined}
        aria-label={sidebarOpen ? t('a11y.navigation_menu') : undefined}
        tabIndex={sidebarOpen ? -1 : undefined}
        className={cn(
          'fixed inset-y-0 left-0 z-40 w-72 bg-card/95 backdrop-blur-xl border-r border-border',
          sidebarCollapsed && 'lg:w-16',
          'transform transition-transform duration-300 ease-in-out',
          'lg:translate-x-0',
          sidebarOpen ? 'translate-x-0' : '-translate-x-full',
        )}
      >
        <div className="flex flex-col h-full">
          {/* Brand — Option C: mark-dominant */}
          <div
            className={cn(
              'border-b border-border',
              sidebarCollapsed ? 'p-3 lg:p-2' : 'p-5',
            )}
          >
            <div
              className={cn(
                'flex items-center gap-3',
                sidebarCollapsed && 'lg:flex-col lg:items-center lg:gap-2',
              )}
            >
              <BrandMarkTile size={sidebarCollapsed ? 40 : 56} className="shrink-0" />
              <div className={cn('min-w-0', sidebarCollapsed && 'lg:hidden')}>
                {/* Not a heading: the shell renders on every route, so an <h1>
                    here collides with the page's own <h1> (PX-290). */}
                <p className="text-sm font-bold text-foreground leading-snug">
                  {t('brand.product_name', 'Quality Governance Platform')}
                </p>
                <p className="text-xs text-muted-foreground mt-0.5 leading-snug">
                  {t('brand.company_line', 'Plantexpand Limited')}
                </p>
              </div>
              <button
                type="button"
                data-testid="nav-sidebar-collapse"
                onClick={toggleSidebar}
                className={cn(
                  'hidden lg:inline-flex shrink-0 items-center justify-center rounded-lg p-2',
                  'text-muted-foreground hover:text-foreground hover:bg-surface transition-colors',
                  !sidebarCollapsed && 'ml-auto',
                )}
                {...iconOnlyControlProps(
                  sidebarCollapsed
                    ? t('a11y.expand_sidebar', { defaultValue: 'Expand sidebar' })
                    : t('a11y.collapse_sidebar', { defaultValue: 'Collapse sidebar' }),
                )}
              >
                {sidebarCollapsed ? (
                  <PanelLeft className="w-5 h-5" aria-hidden="true" />
                ) : (
                  <PanelLeftClose className="w-5 h-5" aria-hidden="true" />
                )}
              </button>
            </div>
          </div>

          {/* Navigation */}
          <nav
            className={cn('flex-1 overflow-y-auto', sidebarCollapsed ? 'p-2 lg:p-2' : 'p-4')}
            aria-label={t('a11y.navigation_menu')}
          >
            <div className="space-y-1">
              <NavLink
                to="/dashboard"
                onClick={() => setSidebarOpen(false)}
                title={sidebarCollapsed ? t('nav.home') : undefined}
                className={({ isActive }) =>
                  cn(
                    'flex items-center gap-3 px-4 py-2.5 rounded-xl text-sm font-medium',
                    'transition-all duration-200 group',
                    sidebarCollapsed && 'lg:justify-center lg:px-2 lg:gap-0',
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
                        'w-5 h-5 transition-colors shrink-0',
                        isActive
                          ? 'text-primary'
                          : 'text-muted-foreground group-hover:text-foreground',
                      )}
                      aria-hidden="true"
                    />
                    <span className={cn(sidebarCollapsed && 'lg:sr-only')}>{t('nav.home')}</span>
                    {isActive && (
                      <div
                        className={cn(
                          'ml-auto w-1.5 h-1.5 rounded-full bg-primary',
                          sidebarCollapsed && 'lg:hidden',
                        )}
                      />
                    )}
                  </>
                )}
              </NavLink>

              {hubs.map((hub) => {
                const expanded = expandedHubs[hub.id] ?? false
                const active = hubIsActive(hub)

                return (
                  <Fragment key={hub.id}>
                    <div className="w-full" data-testid={`nav-hub-${hub.id}`}>
                      <button
                        type="button"
                        onClick={() => {
                          if (sidebarCollapsed && isDesktop) return
                          setExpandedHubs((current) => ({
                            ...current,
                            [hub.id]: !expanded,
                          }))
                        }}
                        aria-expanded={expanded}
                        aria-controls={`nav-hub-${hub.id}`}
                        data-testid={`nav-hub-btn-${hub.id}`}
                        title={sidebarCollapsed ? hub.title : undefined}
                        className={cn(
                          'relative flex w-full items-center gap-3 px-4 py-2.5 rounded-xl text-sm font-medium text-left',
                          'transition-all duration-200 group',
                          sidebarCollapsed && 'lg:justify-center lg:px-2 lg:gap-0',
                          active
                            ? 'bg-primary/10 text-primary'
                            : 'text-muted-foreground hover:text-foreground hover:bg-surface',
                        )}
                      >
                        <hub.icon
                          className={cn(
                            'w-5 h-5 shrink-0 transition-colors',
                            active
                              ? 'text-primary'
                              : 'text-muted-foreground group-hover:text-foreground',
                          )}
                          aria-hidden="true"
                        />
                        <span className={cn('min-w-0 flex-1 leading-snug', sidebarCollapsed && 'lg:sr-only')}>
                          {hub.title}
                        </span>
                        {hub.id === 'admin' && pendingSafetyLookups > 0 ? (
                          <span
                            className={cn(
                              'inline-flex min-w-[1.25rem] items-center justify-center rounded-full bg-destructive px-1.5 py-0.5 text-[10px] font-bold text-destructive-foreground',
                              sidebarCollapsed && 'lg:absolute lg:top-1 lg:right-1 lg:min-w-[0.625rem] lg:h-2.5 lg:w-2.5 lg:px-0 lg:py-0 lg:text-[0px]',
                            )}
                            data-testid="nav-admin-pending-lookups-badge"
                            aria-label={`${pendingSafetyLookups} Safety lookups awaiting approval`}
                          >
                            {pendingSafetyLookups > 99 ? '99+' : pendingSafetyLookups}
                          </span>
                        ) : null}
                        <ChevronDown
                          className={cn(
                            'w-4 h-4 shrink-0 transition-transform',
                            expanded ? 'rotate-0' : '-rotate-90',
                            sidebarCollapsed && 'lg:hidden',
                          )}
                          aria-hidden="true"
                        />
                      </button>

                      {expanded && (
                        <div
                          id={`nav-hub-${hub.id}`}
                          className={cn('mt-1 space-y-1 pl-4', sidebarCollapsed && 'lg:hidden')}
                        >
                          {hub.items.map((item, itemIndex) => {
                            const itemActive =
                              navItemIsActive(
                                item.path,
                                location.pathname,
                                location.search,
                              ) ||
                              (item.path === '/documents' && pathIsActive('/policies'))
                            const previous = hub.items[itemIndex - 1]
                            const showGroupLabel =
                              Boolean(item.group) && item.group !== previous?.group
                            const groupLabel =
                              item.group === 'fleet-assets'
                                ? t('nav.fleet_assets_group', {
                                    defaultValue: 'Fleet & assets',
                                  })
                                : item.group
                                  ? t(`nav.group_${item.group}`, { defaultValue: item.group })
                                  : null
                            return (
                              <Fragment key={item.path}>
                                {showGroupLabel && groupLabel ? (
                                  <div
                                    className="px-4 pt-2 pb-1 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground/80"
                                    data-testid={`nav-group-${item.group}`}
                                  >
                                    {groupLabel}
                                  </div>
                                ) : null}
                                <NavLink
                                  to={item.path}
                                  onClick={() => setSidebarOpen(false)}
                                  aria-current={itemActive ? 'page' : undefined}
                                  className={cn(
                                    'flex items-center gap-3 px-4 py-2 rounded-xl text-sm font-medium',
                                    'transition-all duration-200 group',
                                    item.group && 'ml-2 border-l border-border/60 pl-3',
                                    itemActive
                                      ? 'bg-primary/10 text-primary border border-primary/20'
                                      : 'text-muted-foreground hover:text-foreground hover:bg-surface',
                                  )}
                                >
                                  <item.icon
                                    className={cn(
                                      'w-4 h-4 shrink-0 transition-colors',
                                      itemActive
                                        ? 'text-primary'
                                        : 'text-muted-foreground group-hover:text-foreground',
                                    )}
                                  />
                                  <span className="min-w-0 flex-1 leading-snug">{item.label}</span>
                                  {item.path === '/admin/lookups' && pendingSafetyLookups > 0 ? (
                                    <span
                                      className="inline-flex min-w-[1.25rem] items-center justify-center rounded-full bg-destructive px-1.5 py-0.5 text-[10px] font-bold text-destructive-foreground"
                                      data-testid="nav-lookups-pending-badge"
                                      aria-label={`${pendingSafetyLookups} pending`}
                                    >
                                      {pendingSafetyLookups > 99 ? '99+' : pendingSafetyLookups}
                                    </span>
                                  ) : null}
                                  {itemActive && (
                                    <div className="ml-auto w-1.5 h-1.5 rounded-full bg-primary" />
                                  )}
                                </NavLink>
                              </Fragment>
                            )
                          })}
                        </div>
                      )}
                    </div>
                  </Fragment>
                )
              })}
            </div>
          </nav>

          {/* Footer */}
          <div className={cn('border-t border-border', sidebarCollapsed ? 'p-2 lg:p-2' : 'p-4')}>
            <button
              onClick={onLogout}
              title={sidebarCollapsed ? t('logout') : undefined}
              className={cn(
                'flex items-center gap-3 px-4 py-3 w-full rounded-xl text-sm font-medium',
                'text-muted-foreground hover:text-destructive hover:bg-destructive/10 transition-all duration-200',
                sidebarCollapsed && 'lg:justify-center lg:px-2 lg:gap-0',
              )}
            >
              <LogOut size={20} aria-hidden="true" />
              <span className={cn(sidebarCollapsed && 'lg:sr-only')}>{t('logout')}</span>
            </button>
          </div>
        </div>
      </aside>

      {/* Main content */}
      <main
        id="main-content"
        aria-hidden={sidebarOpen || undefined}
        {...(sidebarOpen ? INERT_PROPS : {})}
        className={cn('pt-16', sidebarCollapsed ? 'lg:pl-16' : 'lg:pl-72')}
      >
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

      {/* PlantEx Assist — code-split; mount only when enabled and opened */}
      {copilotDemoEnabled && copilotOpen ? (
        <Suspense fallback={null}>
          <AICopilot
            isOpen={copilotOpen}
            onClose={() => setCopilotOpen(false)}
            currentPage={window.location.pathname}
          />
        </Suspense>
      ) : null}

      {/* Global keyboard shortcut help (Shift+?) */}
      <KeyboardShortcutHelp />

      {/* Offline status indicator */}
      <OfflineIndicator />

      {/* Session about to end — warn before the 401 interceptor redirects */}
      {sessionExpiryImminent && onExtendSession ? (
        <Suspense fallback={null}>
          <SessionExpiryWarning
            extending={sessionExtending}
            onExtend={onExtendSession}
          />
        </Suspense>
      ) : null}
    </div>
  )
}

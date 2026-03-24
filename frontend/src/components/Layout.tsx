import { Outlet, NavLink, useNavigate } from 'react-router-dom'
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
  History,
  Calendar,
  Bell,
  Download,
  Settings,
  Command,
  GitBranch,
  Brain,
  GitMerge,
  Target,
  Award,
  Leaf,
  FileSignature,
  Bot,
} from 'lucide-react'
import { useState, useEffect, useCallback } from 'react'
import { useTranslation } from 'react-i18next'
import { notificationsApi } from '../api/client'
import AICopilot from './copilot/AICopilot'
import OfflineIndicator from './OfflineIndicator'
import { ThemeToggle } from './ui/ThemeToggle'
import { Button } from './ui/Button'
import { cn } from '../helpers/utils'
import { hasRole, isSuperuser } from '../utils/auth'
import { useFeatureFlag } from '../hooks/useFeatureFlag'

interface LayoutProps {
  onLogout: () => void
}

export default function Layout({ onLogout }: LayoutProps) {
  const { t } = useTranslation()
  const canAccessWorkforce = hasRole('admin', 'supervisor')
  const canManageUsers = isSuperuser()
  const adminUserManagementEnabled = useFeatureFlag('admin_user_management')

  const navSections = [
    {
      title: t('nav.core'),
      items: [
        { path: '/dashboard', icon: LayoutDashboard, label: t('nav.dashboard') },
        { path: '/incidents', icon: AlertTriangle, label: t('nav.incidents') },
        { path: '/near-misses', icon: AlertTriangle, label: t('nav.near_misses') },
        { path: '/rtas', icon: Car, label: t('nav.rtas') },
        { path: '/complaints', icon: MessageSquare, label: t('nav.complaints') },
        { path: '/vehicle-checklists', icon: Truck, label: t('nav.vehicle_checklists') },
      ],
    },
    {
      title: t('nav.workforce'),
      items: [
        { path: '/workforce/assessments', icon: ClipboardCheck, label: t('nav.assessments') },
        { path: '/workforce/training', icon: GraduationCap, label: t('nav.training') },
        { path: '/workforce/engineers', icon: Users, label: t('nav.engineers') },
        { path: '/workforce/calendar', icon: Calendar, label: t('nav.calendar') },
        { path: '/workforce/dashboard', icon: BarChart3, label: t('nav.competency') },
      ],
    },
    {
      title: t('nav.governance'),
      items: [
        { path: '/audits', icon: ClipboardCheck, label: t('nav.audits') },
        { path: '/audit-templates', icon: Sparkles, label: t('nav.audit_builder') },
        { path: '/compliance', icon: Shield, label: t('nav.iso_compliance') },
        { path: '/uvdb', icon: Award, label: t('nav.uvdb_achilles') },
        { path: '/planet-mark', icon: Leaf, label: t('nav.planet_mark') },
        { path: '/investigations', icon: FlaskConical, label: t('nav.investigations') },
        { path: '/standards', icon: BookOpen, label: t('nav.standards') },
        { path: '/actions', icon: ListTodo, label: t('nav.actions') },
      ],
    },
    {
      title: t('nav.library'),
      items: [
        { path: '/documents', icon: FolderOpen, label: t('nav.documents') },
        { path: '/policies', icon: FileText, label: t('nav.policies') },
        { path: '/risks', icon: Shield, label: t('nav.risks') },
      ],
    },
    {
      title: t('nav.enterprise'),
      items: [
        { path: '/risk-register', icon: Target, label: t('nav.risk_register') },
        { path: '/ims', icon: GitMerge, label: t('nav.ims_dashboard') },
        { path: '/ai-intelligence', icon: Brain, label: t('nav.ai_intelligence') },
      ],
    },
    {
      title: t('nav.analytics'),
      items: [
        { path: '/analytics', icon: BarChart3, label: t('nav.overview') },
        { path: '/analytics/advanced', icon: BarChart3, label: t('nav.advanced_analytics') },
        { path: '/analytics/dashboards', icon: LayoutDashboard, label: t('nav.dashboard_builder') },
        { path: '/analytics/reports', icon: FileText, label: t('nav.report_generator') },
        { path: '/calendar', icon: Calendar, label: t('nav.calendar') },
        { path: '/exports', icon: Download, label: t('nav.export_center') },
      ],
    },
    {
      title: t('nav.automation'),
      items: [
        { path: '/workflows', icon: GitBranch, label: t('nav.workflow_center') },
        { path: '/compliance-automation', icon: Shield, label: t('nav.compliance_automation') },
        { path: '/signatures', icon: FileSignature, label: t('nav.digital_signatures') },
      ],
    },
    {
      title: t('nav.admin'),
      items: [
        ...(canManageUsers && adminUserManagementEnabled
          ? [{ path: '/admin/users', icon: Users, label: t('nav.user_management') }]
          : []),
        { path: '/audit-trail', icon: History, label: t('nav.audit_trail') },
      ],
    },
  ].filter((section) => canAccessWorkforce || section.title !== t('nav.workforce'))
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
            {navSections.map((section) => (
              <div key={section.title} className="mb-6">
                <h3 className="px-4 text-2xs font-bold text-muted-foreground uppercase tracking-wider mb-2">
                  {section.title}
                </h3>
                <div className="space-y-1">
                  {section.items.map((item) => (
                    <NavLink
                      key={item.path}
                      to={item.path}
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
                          <item.icon
                            className={cn(
                              'w-5 h-5 transition-colors',
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
              </div>
            ))}
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

      {/* AI Copilot */}
      <AICopilot
        isOpen={copilotOpen}
        onClose={() => setCopilotOpen(false)}
        currentPage={window.location.pathname}
      />

      {/* Offline status indicator */}
      <OfflineIndicator />
    </div>
  )
}

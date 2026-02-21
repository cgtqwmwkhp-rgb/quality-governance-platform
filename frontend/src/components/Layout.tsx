import { Outlet, NavLink, useNavigate } from 'react-router-dom'
import { 
  LayoutDashboard, 
  AlertTriangle, 
  FileText, 
  Shield,
  Car,
  MessageSquare,
  ClipboardCheck,
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
import { useState, useMemo } from 'react'
import AICopilot from './copilot/AICopilot'
import KeyboardShortcutHelp from './KeyboardShortcutHelp'
import { ThemeToggle } from './ui/ThemeToggle'
import { Button } from './ui/Button'
import { cn } from "../helpers/utils"
import { useKeyboardShortcuts } from '../hooks/useKeyboardShortcuts'

interface LayoutProps {
  onLogout: () => void
}

const navSections = [
  {
    title: 'Core',
    items: [
      { path: '/dashboard', icon: LayoutDashboard, label: 'Dashboard' },
      { path: '/incidents', icon: AlertTriangle, label: 'Incidents' },
      { path: '/rtas', icon: Car, label: 'RTAs' },
      { path: '/complaints', icon: MessageSquare, label: 'Complaints' },
    ]
  },
  {
    title: 'Governance',
    items: [
      { path: '/audits', icon: ClipboardCheck, label: 'Audits' },
      { path: '/audit-templates', icon: Sparkles, label: 'Audit Builder' },
      { path: '/risk-register', icon: Target, label: 'Risk Register' },
      { path: '/compliance', icon: Shield, label: 'ISO Compliance' },
      { path: '/uvdb', icon: Award, label: 'UVDB Achilles' },
      { path: '/planet-mark', icon: Leaf, label: 'Planet Mark' },
      { path: '/investigations', icon: FlaskConical, label: 'Investigations' },
      { path: '/standards', icon: BookOpen, label: 'Standards' },
      { path: '/actions', icon: ListTodo, label: 'Actions' },
    ]
  },
  {
    title: 'Library',
    items: [
      { path: '/documents', icon: FolderOpen, label: 'Documents' },
      { path: '/policies', icon: FileText, label: 'Policies' },
    ]
  },
  {
    title: 'Enterprise',
    items: [
      { path: '/ims', icon: GitMerge, label: 'IMS Dashboard' },
      { path: '/ai-intelligence', icon: Brain, label: 'AI Intelligence' },
    ]
  },
  {
    title: 'Analytics',
    items: [
      { path: '/analytics', icon: BarChart3, label: 'Overview' },
      { path: '/analytics/advanced', icon: BarChart3, label: 'Advanced Analytics' },
      { path: '/analytics/dashboards', icon: LayoutDashboard, label: 'Dashboard Builder' },
      { path: '/analytics/reports', icon: FileText, label: 'Report Generator' },
      { path: '/calendar', icon: Calendar, label: 'Calendar' },
      { path: '/exports', icon: Download, label: 'Export Center' },
    ]
  },
  {
    title: 'Automation',
    items: [
      { path: '/workflows', icon: GitBranch, label: 'Workflow Center' },
      { path: '/compliance-automation', icon: Shield, label: 'Compliance Automation' },
      { path: '/signatures', icon: FileSignature, label: 'Digital Signatures' },
    ]
  },
  {
    title: 'Admin',
    items: [
      { path: '/users', icon: Users, label: 'User Management' },
      { path: '/audit-trail', icon: History, label: 'Audit Trail' },
    ]
  }
]

export default function Layout({ onLogout }: LayoutProps) {
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [unreadNotifications] = useState(3)
  const [copilotOpen, setCopilotOpen] = useState(false)
  const navigate = useNavigate()

  const shortcuts = useMemo(() => [
    {
      key: 'k',
      modifiers: ['meta' as const],
      description: 'Open global search',
      action: () => navigate('/search'),
      scope: 'Navigation',
    },
  ], [navigate])

  useKeyboardShortcuts(shortcuts)

  return (
    <div className="min-h-screen bg-background">
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:absolute focus:top-4 focus:left-4 focus:z-50 focus:px-4 focus:py-2 focus:bg-blue-600 focus:text-white focus:rounded-md focus:outline-none"
      >
        Skip to main content
      </a>

      {/* Top Bar */}
      <header role="banner" aria-label="Site header" className="fixed top-0 right-0 left-0 lg:left-72 h-16 bg-card/95 backdrop-blur-lg border-b border-border z-30 flex items-center justify-between px-4 sm:px-6">
        {/* Search Bar */}
        <button
          onClick={() => navigate('/search')}
          aria-label="Open global search"
          className={cn(
            "flex items-center gap-3 px-4 py-2 rounded-lg text-muted-foreground",
            "bg-surface border border-border",
            "hover:text-foreground hover:border-border-strong transition-all",
            "w-full max-w-md"
          )}
        >
          <Search className="w-4 h-4" />
          <span className="text-sm">Search...</span>
          <div className="ml-auto flex items-center gap-1 text-xs text-muted-foreground">
            <Command className="w-3 h-3" />
            <span>K</span>
          </div>
        </button>
        
        {/* Right Actions */}
        <div className="flex items-center gap-2">
          {/* Theme Toggle */}
          <ThemeToggle />
          
          <NavLink
            to="/notifications"
            aria-label={`Notifications${unreadNotifications > 0 ? ` (${unreadNotifications} unread)` : ''}`}
            className={cn(
              "relative p-2 rounded-lg transition-colors",
              "text-muted-foreground hover:text-foreground hover:bg-surface"
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
            to="/users"
            aria-label="Settings"
            className="p-2 text-muted-foreground hover:text-foreground hover:bg-surface rounded-lg transition-colors"
          >
            <Settings className="w-5 h-5" />
          </NavLink>
          
          {/* AI Copilot Toggle */}
          <Button
            onClick={() => setCopilotOpen(!copilotOpen)}
            variant={copilotOpen ? 'default' : 'ghost'}
            size="sm"
            className={cn(
              "gap-2",
              copilotOpen && "shadow-glow"
            )}
          >
            <Bot className="w-4 h-4" />
            <span className="hidden sm:inline">Copilot</span>
          </Button>
        </div>
      </header>

      {/* Mobile menu button */}
      <button
        onClick={() => setSidebarOpen(!sidebarOpen)}
        aria-label={sidebarOpen ? 'Close navigation menu' : 'Open navigation menu'}
        aria-expanded={sidebarOpen}
        className="lg:hidden fixed top-4 left-4 z-50 p-2 rounded-lg bg-card border border-border text-foreground shadow-sm"
      >
        {sidebarOpen ? <X size={24} /> : <Menu size={24} />}
      </button>

      {/* Sidebar */}
      <aside aria-label="Main navigation" className={cn(
        "fixed inset-y-0 left-0 z-40 w-72 bg-card/95 backdrop-blur-xl border-r border-border",
        "transform transition-transform duration-300 ease-in-out",
        "lg:translate-x-0",
        sidebarOpen ? 'translate-x-0' : '-translate-x-full'
      )}>
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
                <p className="text-xs text-muted-foreground">Quality Governance Platform</p>
              </div>
            </div>
          </div>

          {/* Navigation */}
          <nav aria-label="Main navigation" className="flex-1 p-4 overflow-y-auto">
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
                      className={({ isActive }) => cn(
                        "flex items-center gap-3 px-4 py-2.5 rounded-xl text-sm font-medium",
                        "transition-all duration-200 group",
                        isActive
                          ? "bg-primary/10 text-primary border border-primary/20"
                          : "text-muted-foreground hover:text-foreground hover:bg-surface"
                      )}
                    >
                      {({ isActive }) => (
                        <>
                          <item.icon className={cn(
                            "w-5 h-5 transition-colors",
                            isActive ? "text-primary" : "text-muted-foreground group-hover:text-foreground"
                          )} />
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
                "flex items-center gap-3 px-4 py-3 w-full rounded-xl text-sm font-medium",
                "text-muted-foreground hover:text-destructive hover:bg-destructive/10 transition-all duration-200"
              )}
            >
              <LogOut size={20} />
              Sign Out
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
          aria-hidden="true"
          onClick={() => setSidebarOpen(false)}
        />
      )}
      
      {/* AI Copilot */}
      <AICopilot 
        isOpen={copilotOpen} 
        onClose={() => setCopilotOpen(false)}
        currentPage={window.location.pathname}
      />

      {/* Keyboard Shortcut Help (? key) */}
      <KeyboardShortcutHelp />
    </div>
  )
}

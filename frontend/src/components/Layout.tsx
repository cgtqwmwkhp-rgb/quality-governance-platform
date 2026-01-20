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
  Target
} from 'lucide-react'
import { useState, useEffect } from 'react'

interface LayoutProps {
  onLogout: () => void
}

const navSections = [
  {
    title: 'Core',
    items: [
      { path: '/dashboard', icon: LayoutDashboard, label: 'Dashboard', color: 'text-emerald-400' },
      { path: '/incidents', icon: AlertTriangle, label: 'Incidents', color: 'text-amber-400' },
      { path: '/rtas', icon: Car, label: 'RTAs', color: 'text-orange-400' },
      { path: '/complaints', icon: MessageSquare, label: 'Complaints', color: 'text-purple-400' },
    ]
  },
  {
    title: 'Governance',
    items: [
      { path: '/audits', icon: ClipboardCheck, label: 'Audits', color: 'text-indigo-400' },
      { path: '/audit-templates', icon: Sparkles, label: 'Audit Builder', color: 'text-pink-400' },
      { path: '/compliance', icon: Shield, label: 'ISO Compliance', color: 'text-emerald-400' },
      { path: '/investigations', icon: FlaskConical, label: 'Investigations', color: 'text-violet-400' },
      { path: '/standards', icon: BookOpen, label: 'Standards', color: 'text-cyan-400' },
      { path: '/actions', icon: ListTodo, label: 'Actions', color: 'text-teal-400' },
    ]
  },
  {
    title: 'Library',
    items: [
      { path: '/documents', icon: FolderOpen, label: 'Documents', color: 'text-sky-400' },
      { path: '/policies', icon: FileText, label: 'Policies', color: 'text-blue-400' },
      { path: '/risks', icon: Shield, label: 'Risks', color: 'text-rose-400' },
    ]
  },
  {
    title: 'Enterprise',
    items: [
      { path: '/risk-register', icon: Target, label: 'Risk Register', color: 'text-red-400' },
      { path: '/ims', icon: GitMerge, label: 'IMS Dashboard', color: 'text-emerald-400' },
      { path: '/ai-intelligence', icon: Brain, label: 'AI Intelligence', color: 'text-purple-400' },
    ]
  },
  {
    title: 'Analytics',
    items: [
      { path: '/analytics', icon: BarChart3, label: 'Overview', color: 'text-violet-400' },
      { path: '/analytics/advanced', icon: BarChart3, label: 'Advanced Analytics', color: 'text-emerald-400' },
      { path: '/analytics/dashboards', icon: LayoutDashboard, label: 'Dashboard Builder', color: 'text-blue-400' },
      { path: '/analytics/reports', icon: FileText, label: 'Report Generator', color: 'text-amber-400' },
      { path: '/calendar', icon: Calendar, label: 'Calendar', color: 'text-rose-400' },
      { path: '/exports', icon: Download, label: 'Export Center', color: 'text-teal-400' },
    ]
  },
  {
    title: 'Automation',
    items: [
      { path: '/workflows', icon: GitBranch, label: 'Workflow Center', color: 'text-purple-400' },
      { path: '/compliance-automation', icon: Shield, label: 'Compliance Automation', color: 'text-emerald-400' },
    ]
  },
  {
    title: 'Admin',
    items: [
      { path: '/users', icon: Users, label: 'User Management', color: 'text-indigo-400' },
      { path: '/audit-trail', icon: History, label: 'Audit Trail', color: 'text-cyan-400' },
    ]
  }
]

export default function Layout({ onLogout }: LayoutProps) {
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [unreadNotifications] = useState(3)
  const navigate = useNavigate()

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
    <div className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950">
      {/* Top Bar */}
      <div className="fixed top-0 right-0 left-0 lg:left-72 h-16 bg-slate-900/80 backdrop-blur-xl border-b border-slate-800 z-30 flex items-center justify-between px-6">
        {/* Search Bar */}
        <button
          onClick={() => navigate('/search')}
          className="flex items-center gap-3 px-4 py-2 bg-slate-800/50 border border-slate-700 rounded-xl text-slate-400 hover:text-white hover:border-slate-600 transition-all w-full max-w-md"
        >
          <Search className="w-4 h-4" />
          <span className="text-sm">Search...</span>
          <div className="ml-auto flex items-center gap-1 text-xs text-slate-500">
            <Command className="w-3 h-3" />
            <span>K</span>
          </div>
        </button>
        
        {/* Right Actions */}
        <div className="flex items-center gap-3">
          <NavLink
            to="/notifications"
            className="relative p-2 text-slate-400 hover:text-white hover:bg-slate-800/50 rounded-lg transition-all"
          >
            <Bell className="w-5 h-5" />
            {unreadNotifications > 0 && (
              <span className="absolute -top-0.5 -right-0.5 w-4 h-4 bg-red-500 text-white text-[10px] font-bold rounded-full flex items-center justify-center">
                {unreadNotifications}
              </span>
            )}
          </NavLink>
          
          <NavLink
            to="/users"
            className="p-2 text-slate-400 hover:text-white hover:bg-slate-800/50 rounded-lg transition-all"
          >
            <Settings className="w-5 h-5" />
          </NavLink>
        </div>
      </div>

      {/* Mobile menu button */}
      <button
        onClick={() => setSidebarOpen(!sidebarOpen)}
        className="lg:hidden fixed top-4 left-4 z-50 p-2 rounded-lg bg-slate-800 text-white"
      >
        {sidebarOpen ? <X size={24} /> : <Menu size={24} />}
      </button>

      {/* Sidebar */}
      <aside className={`
        fixed inset-y-0 left-0 z-40 w-72 bg-slate-900/95 backdrop-blur-xl border-r border-slate-800
        transform transition-transform duration-300 ease-in-out
        lg:translate-x-0 ${sidebarOpen ? 'translate-x-0' : '-translate-x-full'}
      `}>
        <div className="flex flex-col h-full">
          {/* Logo */}
          <div className="p-6 border-b border-slate-800">
            <div className="flex items-center gap-3">
              <div className="w-11 h-11 rounded-xl bg-gradient-to-br from-emerald-400 via-teal-500 to-cyan-500 
                flex items-center justify-center shadow-lg shadow-emerald-500/20">
                <Shield className="w-6 h-6 text-white" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h1 className="text-lg font-bold text-white">QGP</h1>
                  <span className="px-1.5 py-0.5 text-[10px] font-bold bg-gradient-to-r from-emerald-500 to-teal-500 
                    text-white rounded-full flex items-center gap-0.5">
                    <Sparkles className="w-2.5 h-2.5" />
                    PRO
                  </span>
                </div>
                <p className="text-xs text-slate-400">Quality Governance Platform</p>
              </div>
            </div>
          </div>

          {/* Navigation */}
          <nav className="flex-1 p-4 overflow-y-auto">
            {navSections.map((section) => (
              <div key={section.title} className="mb-6">
                <h3 className="px-4 text-[10px] font-bold text-slate-500 uppercase tracking-wider mb-2">
                  {section.title}
                </h3>
                <div className="space-y-1">
                  {section.items.map((item) => (
                    <NavLink
                      key={item.path}
                      to={item.path}
                      onClick={() => setSidebarOpen(false)}
                      className={({ isActive }) => `
                        flex items-center gap-3 px-4 py-2.5 rounded-xl text-sm font-medium
                        transition-all duration-200 group
                        ${isActive
                          ? 'bg-gradient-to-r from-slate-800 to-slate-800/50 text-white shadow-lg border border-slate-700/50'
                          : 'text-slate-400 hover:text-white hover:bg-slate-800/50'
                        }
                      `}
                    >
                      {({ isActive }) => (
                        <>
                          <item.icon className={`w-5 h-5 transition-colors ${isActive ? item.color : 'text-slate-500 group-hover:text-slate-300'}`} />
                          {item.label}
                          {isActive && (
                            <div className={`ml-auto w-1.5 h-1.5 rounded-full bg-current ${item.color}`} />
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
          <div className="p-4 border-t border-slate-800">
            <button
              onClick={onLogout}
              className="flex items-center gap-3 px-4 py-3 w-full rounded-xl text-sm font-medium
                text-slate-400 hover:text-red-400 hover:bg-red-500/10 transition-all duration-200"
            >
              <LogOut size={20} />
              Sign Out
            </button>
          </div>
        </div>
      </aside>

      {/* Main content */}
      <main className="lg:pl-72 pt-16">
        <div className="p-6 lg:p-8 min-h-screen">
          <Outlet />
        </div>
      </main>

      {/* Mobile overlay */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-30 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}
    </div>
  )
}

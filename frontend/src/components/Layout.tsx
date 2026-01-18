import { Outlet, NavLink } from 'react-router-dom'
import { 
  LayoutDashboard, 
  AlertTriangle, 
  FileText, 
  Shield, 
  
  LogOut,
  Menu,
  X
} from 'lucide-react'
import { useState } from 'react'

interface LayoutProps {
  onLogout: () => void
}

const navItems = [
  { path: '/dashboard', icon: LayoutDashboard, label: 'Dashboard' },
  { path: '/incidents', icon: AlertTriangle, label: 'Incidents' },
  { path: '/policies', icon: FileText, label: 'Policies', disabled: true },
  { path: '/risks', icon: Shield, label: 'Risks', disabled: true },
]

export default function Layout({ onLogout }: LayoutProps) {
  const [sidebarOpen, setSidebarOpen] = useState(false)

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950">
      {/* Mobile menu button */}
      <button
        onClick={() => setSidebarOpen(!sidebarOpen)}
        className="lg:hidden fixed top-4 left-4 z-50 p-2 rounded-lg bg-slate-800 text-white"
      >
        {sidebarOpen ? <X size={24} /> : <Menu size={24} />}
      </button>

      {/* Sidebar */}
      <aside className={`
        fixed inset-y-0 left-0 z-40 w-64 bg-slate-900/95 backdrop-blur-xl border-r border-slate-800
        transform transition-transform duration-300 ease-in-out
        lg:translate-x-0 ${sidebarOpen ? 'translate-x-0' : '-translate-x-full'}
      `}>
        <div className="flex flex-col h-full">
          {/* Logo */}
          <div className="p-6 border-b border-slate-800">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-emerald-400 to-teal-500 flex items-center justify-center">
                <Shield className="w-6 h-6 text-white" />
              </div>
              <div>
                <h1 className="text-lg font-bold text-white">QGP</h1>
                <p className="text-xs text-slate-400">Quality Governance</p>
              </div>
            </div>
          </div>

          {/* Navigation */}
          <nav className="flex-1 p-4 space-y-1">
            {navItems.map((item) => (
              <NavLink
                key={item.path}
                to={item.disabled ? '#' : item.path}
                onClick={(e) => item.disabled && e.preventDefault()}
                className={({ isActive }) => `
                  flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-medium
                  transition-all duration-200
                  ${item.disabled 
                    ? 'text-slate-600 cursor-not-allowed' 
                    : isActive
                      ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                      : 'text-slate-400 hover:text-white hover:bg-slate-800'
                  }
                `}
              >
                <item.icon size={20} />
                {item.label}
                {item.disabled && (
                  <span className="ml-auto text-xs bg-slate-800 px-2 py-0.5 rounded">Soon</span>
                )}
              </NavLink>
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
      <main className="lg:pl-64">
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

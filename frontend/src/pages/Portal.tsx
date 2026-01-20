import { useNavigate } from 'react-router-dom';
import {
  FileText,
  Search,
  HelpCircle,
  Shield,
  ChevronRight,
  Smartphone,
  LogOut,
  User,
} from 'lucide-react';
import { usePortalAuth } from '../contexts/PortalAuthContext';
import { ThemeToggle } from '../components/ui/ThemeToggle';

// Animated background with purple gradient
const AnimatedBackground = () => (
  <div className="fixed inset-0 -z-10 overflow-hidden">
    <div className="absolute inset-0 bg-gradient-to-br from-slate-900 via-purple-900/50 to-slate-900" />
    <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-purple-500 rounded-full mix-blend-multiply filter blur-3xl opacity-20 animate-pulse" />
    <div className="absolute bottom-1/4 right-1/4 w-96 h-96 bg-indigo-500 rounded-full mix-blend-multiply filter blur-3xl opacity-20 animate-pulse" />
  </div>
);

export default function Portal() {
  const navigate = useNavigate();
  const { user, logout } = usePortalAuth();

  const handleLogout = () => {
    logout();
    navigate('/portal/login');
  };

  return (
    <div className="min-h-screen relative">
      <AnimatedBackground />

      {/* Header with User Info */}
      <header className="sticky top-0 z-50 bg-black/30 backdrop-blur-xl border-b border-white/10">
        <div className="max-w-lg mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 bg-gradient-to-br from-purple-500 to-indigo-600 rounded-xl flex items-center justify-center shadow-lg">
                <Shield className="w-6 h-6 text-white" />
              </div>
              <div>
                <h1 className="text-white font-bold text-lg">Plantexpand</h1>
                <p className="text-gray-400 text-xs">Employee Portal</p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <ThemeToggle />
              <button
                onClick={handleLogout}
                className="p-2 hover:bg-white/10 rounded-lg transition-colors"
                title="Sign out"
              >
                <LogOut className="w-5 h-5 text-gray-400 hover:text-white" />
              </button>
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-lg mx-auto px-4 py-8">
        {/* User Welcome Card */}
        <div className="p-4 mb-6 bg-white/5 backdrop-blur-sm border border-white/10 rounded-2xl">
          <div className="flex items-center gap-3">
            <div className="w-12 h-12 bg-purple-500/20 rounded-full flex items-center justify-center">
              <User className="w-6 h-6 text-purple-400" />
            </div>
            <div className="flex-1">
              <p className="text-white font-semibold">{user?.name || 'Employee'}</p>
              <p className="text-gray-400 text-sm">{user?.email}</p>
              {user?.isDemoUser && (
                <span className="inline-block mt-1 px-2 py-0.5 bg-yellow-500/20 text-yellow-400 text-xs rounded-full">
                  Demo Mode
                </span>
              )}
            </div>
          </div>
        </div>

        {/* Welcome Message */}
        <div className="text-center mb-8">
          <h2 className="text-2xl font-bold text-white mb-2">What would you like to do?</h2>
          <p className="text-gray-400">Select an option below</p>
        </div>

        {/* Main Actions */}
        <div className="space-y-3">
          {/* Primary Action: Submit Report */}
          <button
            onClick={() => navigate('/portal/report')}
            className="w-full flex items-center gap-4 p-5 bg-white/5 hover:bg-white/10 border-2 border-purple-500/30 hover:border-purple-500/50 rounded-2xl transition-all group"
          >
            <div className="w-14 h-14 bg-gradient-to-br from-purple-500 to-indigo-600 rounded-xl flex items-center justify-center shadow-lg">
              <FileText className="w-7 h-7 text-white" />
            </div>
            <div className="flex-1 text-left">
              <h3 className="text-lg font-semibold text-white group-hover:text-purple-300 transition-colors">
                Submit a Report
              </h3>
              <p className="text-sm text-gray-400">Incident, Near Miss, Complaint, or RTA</p>
            </div>
            <ChevronRight className="w-6 h-6 text-purple-400 group-hover:translate-x-1 transition-transform" />
          </button>

          {/* Secondary Action: Track Status */}
          <button
            onClick={() => navigate('/portal/track')}
            className="w-full flex items-center gap-4 p-4 bg-white/5 hover:bg-white/10 border border-white/10 hover:border-white/20 rounded-2xl transition-all group"
          >
            <div className="w-12 h-12 bg-cyan-500/20 rounded-xl flex items-center justify-center">
              <Search className="w-6 h-6 text-cyan-400" />
            </div>
            <div className="flex-1 text-left">
              <h3 className="font-semibold text-white group-hover:text-cyan-300 transition-colors">
                Track My Report
              </h3>
              <p className="text-sm text-gray-400">Check status with reference number</p>
            </div>
            <ChevronRight className="w-5 h-5 text-gray-500 group-hover:translate-x-1 transition-transform" />
          </button>

          {/* Help & Support */}
          <button
            onClick={() => navigate('/portal/help')}
            className="w-full flex items-center gap-4 p-4 bg-white/5 hover:bg-white/10 border border-white/10 hover:border-white/20 rounded-2xl transition-all group"
          >
            <div className="w-12 h-12 bg-indigo-500/20 rounded-xl flex items-center justify-center">
              <HelpCircle className="w-6 h-6 text-indigo-400" />
            </div>
            <div className="flex-1 text-left">
              <h3 className="font-semibold text-white group-hover:text-indigo-300 transition-colors">
                Help & Support
              </h3>
              <p className="text-sm text-gray-400">FAQs and contact information</p>
            </div>
            <ChevronRight className="w-5 h-5 text-gray-500 group-hover:translate-x-1 transition-transform" />
          </button>
        </div>

        {/* Mobile Optimized Badge */}
        <div className="mt-10 flex items-center justify-center gap-2 text-gray-500 text-sm">
          <Smartphone className="w-4 h-4" />
          <span>Optimized for mobile devices</span>
        </div>
      </main>

      {/* Admin Login Link */}
      <footer className="fixed bottom-0 left-0 right-0 p-4 text-center bg-black/30 backdrop-blur-sm border-t border-white/10">
        <button
          onClick={() => navigate('/login')}
          className="text-gray-400 hover:text-white text-sm transition-colors"
        >
          Admin Login →
        </button>
      </footer>
    </div>
  );
}

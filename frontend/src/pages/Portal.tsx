import { useNavigate } from 'react-router-dom';
import {
  FileText,
  Search,
  AlertTriangle,
  HelpCircle,
  Shield,
  ChevronRight,
  Smartphone,
} from 'lucide-react';

export default function Portal() {
  const navigate = useNavigate();

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900/20 to-slate-900">
      {/* Simple Header */}
      <header className="bg-black/20 backdrop-blur-xl border-b border-white/10">
        <div className="max-w-lg mx-auto px-4 py-4 flex items-center justify-center gap-3">
          <div className="w-10 h-10 bg-gradient-to-br from-purple-500 to-cyan-500 rounded-xl flex items-center justify-center">
            <Shield className="w-6 h-6 text-white" />
          </div>
          <div className="text-center">
            <h1 className="text-white font-bold text-lg">Plantexpand</h1>
            <p className="text-gray-400 text-xs">Employee Portal</p>
          </div>
        </div>
      </header>

      <main className="max-w-lg mx-auto px-4 py-8">
        {/* Welcome Message */}
        <div className="text-center mb-8">
          <h2 className="text-2xl font-bold text-white mb-2">Welcome</h2>
          <p className="text-gray-400">What would you like to do?</p>
        </div>

        {/* Main Actions - Clear hierarchy */}
        <div className="space-y-3">
          {/* Primary Action: Submit Report */}
          <button
            onClick={() => navigate('/portal/report')}
            className="w-full flex items-center gap-4 p-5 bg-gradient-to-r from-purple-500/20 to-cyan-500/20 hover:from-purple-500/30 hover:to-cyan-500/30 border-2 border-purple-500/50 rounded-2xl transition-all group"
          >
            <div className="w-14 h-14 bg-gradient-to-br from-purple-500 to-cyan-500 rounded-xl flex items-center justify-center shadow-lg">
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
            <div className="w-12 h-12 bg-blue-500/20 rounded-xl flex items-center justify-center">
              <Search className="w-6 h-6 text-blue-400" />
            </div>
            <div className="flex-1 text-left">
              <h3 className="font-semibold text-white group-hover:text-blue-300 transition-colors">
                Track My Report
              </h3>
              <p className="text-sm text-gray-500">Check status with reference number</p>
            </div>
            <ChevronRight className="w-5 h-5 text-gray-500 group-hover:translate-x-1 transition-transform" />
          </button>

          {/* Emergency SOS */}
          <button
            onClick={() => navigate('/portal/sos')}
            className="w-full flex items-center gap-4 p-4 bg-red-500/10 hover:bg-red-500/20 border border-red-500/30 hover:border-red-500/50 rounded-2xl transition-all group"
          >
            <div className="w-12 h-12 bg-red-500/20 rounded-xl flex items-center justify-center">
              <AlertTriangle className="w-6 h-6 text-red-400" />
            </div>
            <div className="flex-1 text-left">
              <h3 className="font-semibold text-white group-hover:text-red-300 transition-colors">
                Emergency SOS
              </h3>
              <p className="text-sm text-gray-500">Immediate assistance needed</p>
            </div>
            <ChevronRight className="w-5 h-5 text-gray-500 group-hover:translate-x-1 transition-transform" />
          </button>

          {/* Help */}
          <button
            onClick={() => navigate('/portal/help')}
            className="w-full flex items-center gap-4 p-4 bg-white/5 hover:bg-white/10 border border-white/10 hover:border-white/20 rounded-2xl transition-all group"
          >
            <div className="w-12 h-12 bg-gray-500/20 rounded-xl flex items-center justify-center">
              <HelpCircle className="w-6 h-6 text-gray-400" />
            </div>
            <div className="flex-1 text-left">
              <h3 className="font-semibold text-white group-hover:text-gray-300 transition-colors">
                Help & Support
              </h3>
              <p className="text-sm text-gray-500">FAQs and contact information</p>
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
      <footer className="fixed bottom-0 left-0 right-0 p-4 text-center">
        <button
          onClick={() => navigate('/login')}
          className="text-gray-600 hover:text-gray-400 text-sm transition-colors"
        >
          Admin Login →
        </button>
      </footer>
    </div>
  );
}

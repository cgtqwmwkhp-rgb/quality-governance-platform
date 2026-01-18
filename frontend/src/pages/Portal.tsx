import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  AlertTriangle,
  MessageSquare,
  Shield,
  ArrowRight,
  CheckCircle,
  Clock,
  Search,
  Smartphone,
  Lock,
  Eye,
  QrCode,
  Sparkles,
  ChevronRight,
  Star,
  Zap,
  Users,
  TrendingUp,
  HelpCircle,
  Phone,
  Siren,
} from 'lucide-react';

// Animated background gradient component
const AnimatedBackground = () => (
  <div className="fixed inset-0 -z-10 overflow-hidden">
    <div className="absolute inset-0 bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900" />
    <div className="absolute top-0 -left-4 w-96 h-96 bg-purple-500 rounded-full mix-blend-multiply filter blur-3xl opacity-20 animate-blob" />
    <div className="absolute top-0 -right-4 w-96 h-96 bg-cyan-500 rounded-full mix-blend-multiply filter blur-3xl opacity-20 animate-blob animation-delay-2000" />
    <div className="absolute -bottom-8 left-20 w-96 h-96 bg-pink-500 rounded-full mix-blend-multiply filter blur-3xl opacity-20 animate-blob animation-delay-4000" />
    <div className="absolute inset-0 bg-[url('data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNjAiIGhlaWdodD0iNjAiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+PGRlZnM+PHBhdHRlcm4gaWQ9ImdyaWQiIHdpZHRoPSI2MCIgaGVpZ2h0PSI2MCIgcGF0dGVyblVuaXRzPSJ1c2VyU3BhY2VPblVzZSI+PHBhdGggZD0iTSA2MCAwIEwgMCAwIDAgNjAiIGZpbGw9Im5vbmUiIHN0cm9rZT0icmdiYSgyNTUsMjU1LDI1NSwwLjAzKSIgc3Ryb2tlLXdpZHRoPSIxIi8+PC9wYXR0ZXJuPjwvZGVmcz48cmVjdCB3aWR0aD0iMTAwJSIgaGVpZ2h0PSIxMDAlIiBmaWxsPSJ1cmwoI2dyaWQpIi8+PC9zdmc+')] opacity-40" />
  </div>
);

// Stats card component
const StatCard = ({ icon: Icon, value, label, color }: { icon: any; value: string; label: string; color: string }) => (
  <div className="bg-white/5 backdrop-blur-sm border border-white/10 rounded-2xl p-4 text-center">
    <div className={`inline-flex p-2 rounded-xl ${color} mb-2`}>
      <Icon className="w-5 h-5 text-white" />
    </div>
    <div className="text-2xl font-bold text-white">{value}</div>
    <div className="text-xs text-gray-400">{label}</div>
  </div>
);

// Feature card component
const FeatureCard = ({ icon: Icon, title, description }: { icon: any; title: string; description: string }) => (
  <div className="flex items-start gap-3 p-4 bg-white/5 backdrop-blur-sm border border-white/10 rounded-xl hover:bg-white/10 transition-all">
    <div className="p-2 bg-gradient-to-br from-purple-500 to-cyan-500 rounded-lg">
      <Icon className="w-4 h-4 text-white" />
    </div>
    <div>
      <h4 className="font-semibold text-white text-sm">{title}</h4>
      <p className="text-xs text-gray-400 mt-0.5">{description}</p>
    </div>
  </div>
);

export default function Portal() {
  const navigate = useNavigate();
  const [stats, setStats] = useState({
    totalToday: 12,
    avgResolution: '2.4',
    resolvedWeek: 47,
    satisfaction: '98%',
  });

  return (
    <div className="min-h-screen relative">
      <AnimatedBackground />

      {/* Header */}
      <header className="fixed top-0 left-0 right-0 z-50 bg-black/20 backdrop-blur-xl border-b border-white/10">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 bg-gradient-to-br from-purple-500 to-cyan-500 rounded-xl flex items-center justify-center">
                <Shield className="w-6 h-6 text-white" />
              </div>
              <div>
                <h1 className="text-white font-bold text-lg">Employee Portal</h1>
                <p className="text-gray-400 text-xs">Quality & Safety Reporting</p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={() => navigate('/portal/help')}
                className="flex items-center gap-2 px-3 py-2 bg-white/10 hover:bg-white/20 border border-white/20 rounded-xl text-white text-sm transition-all"
              >
                <HelpCircle className="w-4 h-4" />
                <span className="hidden sm:inline">Help</span>
              </button>
              <button
                onClick={() => navigate('/portal/track')}
                className="flex items-center gap-2 px-3 py-2 bg-white/10 hover:bg-white/20 border border-white/20 rounded-xl text-white text-sm transition-all"
              >
                <Search className="w-4 h-4" />
                <span className="hidden sm:inline">Track</span>
              </button>
              <button
                onClick={() => navigate('/portal/sos')}
                className="flex items-center gap-2 px-3 py-2 bg-red-500 hover:bg-red-600 rounded-xl text-white text-sm font-bold transition-all animate-pulse"
              >
                <Phone className="w-4 h-4" />
                <span>SOS</span>
              </button>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="pt-24 pb-12 px-4 sm:px-6 lg:px-8 max-w-7xl mx-auto">
        {/* Hero Section */}
        <div className="text-center mb-12">
          <div className="inline-flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-purple-500/20 to-cyan-500/20 border border-purple-500/30 rounded-full mb-6">
            <Sparkles className="w-4 h-4 text-purple-400" />
            <span className="text-sm text-purple-300">Confidential • Secure • Anonymous</span>
          </div>
          <h2 className="text-4xl sm:text-5xl lg:text-6xl font-bold text-white mb-4">
            Report. Track.{' '}
            <span className="bg-gradient-to-r from-purple-400 via-pink-400 to-cyan-400 bg-clip-text text-transparent">
              Resolve.
            </span>
          </h2>
          <p className="text-lg text-gray-400 max-w-2xl mx-auto mb-8">
            Your voice matters. Report safety incidents or complaints quickly and securely.
            Choose to remain anonymous – we protect your identity.
          </p>

          {/* Live Stats */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 max-w-3xl mx-auto mb-12">
            <StatCard icon={Zap} value={stats.totalToday.toString()} label="Reports Today" color="bg-yellow-500" />
            <StatCard icon={Clock} value={`${stats.avgResolution} days`} label="Avg Resolution" color="bg-green-500" />
            <StatCard icon={CheckCircle} value={stats.resolvedWeek.toString()} label="Resolved This Week" color="bg-blue-500" />
            <StatCard icon={Star} value={stats.satisfaction} label="Satisfaction" color="bg-purple-500" />
          </div>
        </div>

        {/* Report Type Selection */}
        <div className="grid md:grid-cols-2 gap-6 max-w-4xl mx-auto mb-12">
          {/* Incident Report Card */}
          <button
            onClick={() => navigate('/portal/report?type=incident')}
            className="group relative overflow-hidden bg-gradient-to-br from-red-500/20 to-orange-500/20 border border-red-500/30 rounded-3xl p-8 text-left hover:scale-[1.02] transition-all duration-300"
          >
            <div className="absolute inset-0 bg-gradient-to-br from-red-500/10 to-transparent opacity-0 group-hover:opacity-100 transition-opacity" />
            <div className="relative z-10">
              <div className="w-16 h-16 bg-gradient-to-br from-red-500 to-orange-500 rounded-2xl flex items-center justify-center mb-6 shadow-lg shadow-red-500/30">
                <AlertTriangle className="w-8 h-8 text-white" />
              </div>
              <h3 className="text-2xl font-bold text-white mb-2">Safety Incident</h3>
              <p className="text-gray-400 mb-6">
                Report accidents, near-misses, hazards, or any safety concerns in the workplace.
              </p>
              <div className="flex items-center gap-2 text-red-400 font-semibold">
                Report Now <ArrowRight className="w-5 h-5 group-hover:translate-x-2 transition-transform" />
              </div>
            </div>
          </button>

          {/* Complaint Card */}
          <button
            onClick={() => navigate('/portal/report?type=complaint')}
            className="group relative overflow-hidden bg-gradient-to-br from-amber-500/20 to-yellow-500/20 border border-amber-500/30 rounded-3xl p-8 text-left hover:scale-[1.02] transition-all duration-300"
          >
            <div className="absolute inset-0 bg-gradient-to-br from-amber-500/10 to-transparent opacity-0 group-hover:opacity-100 transition-opacity" />
            <div className="relative z-10">
              <div className="w-16 h-16 bg-gradient-to-br from-amber-500 to-yellow-500 rounded-2xl flex items-center justify-center mb-6 shadow-lg shadow-amber-500/30">
                <MessageSquare className="w-8 h-8 text-white" />
              </div>
              <h3 className="text-2xl font-bold text-white mb-2">Complaint</h3>
              <p className="text-gray-400 mb-6">
                Submit feedback about service quality, workplace issues, or policy concerns.
              </p>
              <div className="flex items-center gap-2 text-amber-400 font-semibold">
                Submit Now <ArrowRight className="w-5 h-5 group-hover:translate-x-2 transition-transform" />
              </div>
            </div>
          </button>
        </div>

        {/* Features Grid */}
        <div className="max-w-4xl mx-auto">
          <h3 className="text-center text-white font-semibold mb-6">Why Use the Employee Portal?</h3>
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
            <FeatureCard
              icon={Lock}
              title="100% Anonymous Option"
              description="Your identity is protected. Report without fear."
            />
            <FeatureCard
              icon={Smartphone}
              title="Mobile Optimized"
              description="Report from anywhere on any device."
            />
            <FeatureCard
              icon={Eye}
              title="Real-time Tracking"
              description="Track your report status anytime."
            />
            <FeatureCard
              icon={QrCode}
              title="QR Code Access"
              description="Scan to quickly access report forms."
            />
            <FeatureCard
              icon={Clock}
              title="Fast Response"
              description="Average resolution in under 3 days."
            />
            <FeatureCard
              icon={Shield}
              title="Secure & Encrypted"
              description="Enterprise-grade security for your data."
            />
          </div>
        </div>

        {/* Track Report CTA */}
        <div className="mt-12 max-w-2xl mx-auto">
          <div className="bg-gradient-to-r from-purple-500/20 to-cyan-500/20 border border-purple-500/30 rounded-2xl p-6 text-center">
            <h3 className="text-xl font-bold text-white mb-2">Already Submitted a Report?</h3>
            <p className="text-gray-400 mb-4">Track its status using your reference number</p>
            <button
              onClick={() => navigate('/portal/track')}
              className="inline-flex items-center gap-2 px-6 py-3 bg-gradient-to-r from-purple-500 to-cyan-500 text-white font-semibold rounded-xl hover:opacity-90 transition-opacity"
            >
              <Search className="w-5 h-5" />
              Track My Report
            </button>
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="py-6 border-t border-white/10">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
          <p className="text-gray-500 text-sm">
            © 2026 Quality Governance Platform • All reports are confidential
          </p>
        </div>
      </footer>

      {/* Custom CSS for animations */}
      <style>{`
        @keyframes blob {
          0% { transform: translate(0px, 0px) scale(1); }
          33% { transform: translate(30px, -50px) scale(1.1); }
          66% { transform: translate(-20px, 20px) scale(0.9); }
          100% { transform: translate(0px, 0px) scale(1); }
        }
        .animate-blob {
          animation: blob 7s infinite;
        }
        .animation-delay-2000 {
          animation-delay: 2s;
        }
        .animation-delay-4000 {
          animation-delay: 4s;
        }
      `}</style>
    </div>
  );
}

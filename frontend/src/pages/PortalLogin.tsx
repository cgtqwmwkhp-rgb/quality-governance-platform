import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Shield, Loader2, AlertCircle, CheckCircle, User } from 'lucide-react';
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

export default function PortalLogin() {
  const navigate = useNavigate();
  const { 
    isAuthenticated, 
    isLoading, 
    login, 
    loginWithDemo, 
    error, 
    isAzureADAvailable 
  } = usePortalAuth();

  // Redirect if already authenticated
  useEffect(() => {
    if (isAuthenticated && !isLoading) {
      navigate('/portal');
    }
  }, [isAuthenticated, isLoading, navigate]);

  const handleMicrosoftLogin = async () => {
    await login();
  };

  const handleDemoLogin = () => {
    loginWithDemo();
  };

  if (isLoading) {
    return (
      <div className="min-h-screen relative flex items-center justify-center">
        <AnimatedBackground />
        <div className="text-center">
          <Loader2 className="w-12 h-12 text-purple-400 animate-spin mx-auto mb-4" />
          <p className="text-gray-400">Checking authentication...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen relative flex items-center justify-center p-4">
      <AnimatedBackground />

      {/* Theme Toggle */}
      <div className="absolute top-4 right-4">
        <ThemeToggle />
      </div>

      <div className="max-w-md w-full relative animate-fade-in">
        {/* Logo & Header */}
        <div className="text-center mb-8">
          <div className="w-20 h-20 bg-gradient-to-br from-purple-500 to-indigo-600 rounded-2xl flex items-center justify-center mx-auto mb-6 shadow-lg">
            <Shield className="w-10 h-10 text-white" />
          </div>
          <h1 className="text-3xl font-bold text-white mb-2">Employee Portal</h1>
          <p className="text-gray-400">Sign in with your Plantexpand account</p>
        </div>

        {/* Login Card */}
        <div className="bg-white/5 backdrop-blur-xl border border-white/10 rounded-3xl p-8">
          {/* Error Message */}
          {error && (
            <div className="mb-6 p-4 bg-red-500/10 border border-red-500/20 rounded-xl flex items-start gap-3">
              <AlertCircle className="w-5 h-5 text-red-400 flex-shrink-0 mt-0.5" />
              <div>
                <p className="text-sm text-red-400 font-medium">Sign in issue</p>
                <p className="text-xs text-red-400/70 mt-1">{error}</p>
              </div>
            </div>
          )}

          {/* Microsoft SSO Button */}
          <button
            onClick={handleMicrosoftLogin}
            disabled={isLoading}
            className="w-full flex items-center justify-center gap-3 px-6 py-4 bg-white/5 hover:bg-white/10 border border-white/20 hover:border-white/30 rounded-xl font-medium text-white transition-all"
          >
            {isLoading ? (
              <Loader2 className="w-5 h-5 animate-spin" />
            ) : (
              <>
                {/* Microsoft Logo */}
                <svg className="w-5 h-5" viewBox="0 0 21 21" fill="none">
                  <rect x="1" y="1" width="9" height="9" fill="#F25022" />
                  <rect x="11" y="1" width="9" height="9" fill="#7FBA00" />
                  <rect x="1" y="11" width="9" height="9" fill="#00A4EF" />
                  <rect x="11" y="11" width="9" height="9" fill="#FFB900" />
                </svg>
                Sign in with Microsoft
              </>
            )}
          </button>

          {isAzureADAvailable && (
            <div className="mt-4 text-center">
              <p className="text-xs text-gray-500">
                Use your <span className="text-purple-400 font-medium">@plantexpand.com</span> email
              </p>
            </div>
          )}

          {/* Divider */}
          <div className="my-6 flex items-center gap-4">
            <div className="flex-1 h-px bg-white/10" />
            <span className="text-xs text-gray-500">OR</span>
            <div className="flex-1 h-px bg-white/10" />
          </div>

          {/* Demo Login Button */}
          <button
            onClick={handleDemoLogin}
            className="w-full flex items-center justify-center gap-2 px-6 py-3 bg-purple-500/20 hover:bg-purple-500/30 border border-purple-500/30 hover:border-purple-500/50 rounded-xl font-medium text-purple-400 transition-all"
          >
            <User className="w-4 h-4" />
            Continue as Demo User
          </button>

          <p className="text-xs text-gray-500 text-center mt-3">
            Demo mode allows you to explore all features
          </p>

          {/* Divider */}
          <div className="my-6 flex items-center gap-4">
            <div className="flex-1 h-px bg-white/10" />
            <span className="text-xs text-gray-500">SECURE SIGN-IN</span>
            <div className="flex-1 h-px bg-white/10" />
          </div>

          {/* Info */}
          <div className="space-y-3 text-sm text-gray-400">
            <div className="flex items-start gap-3">
              <div className="w-6 h-6 bg-green-500/20 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5">
                <CheckCircle className="w-3.5 h-3.5 text-green-400" />
              </div>
              <p>Your identity will be recorded with each report for accountability</p>
            </div>
            <div className="flex items-start gap-3">
              <div className="w-6 h-6 bg-green-500/20 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5">
                <CheckCircle className="w-3.5 h-3.5 text-green-400" />
              </div>
              <p>Your name and details will be auto-filled from your profile</p>
            </div>
            <div className="flex items-start gap-3">
              <div className="w-6 h-6 bg-green-500/20 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5">
                <CheckCircle className="w-3.5 h-3.5 text-green-400" />
              </div>
              <p>Track all your submitted reports in one place</p>
            </div>
          </div>
        </div>

        {/* Admin Link */}
        <div className="mt-8 text-center">
          <button
            onClick={() => navigate('/login')}
            className="text-gray-400 hover:text-white text-sm transition-colors"
          >
            Admin Login →
          </button>
        </div>
      </div>
    </div>
  );
}
